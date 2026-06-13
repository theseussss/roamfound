# -*- coding: utf-8 -*-
"""
flow_hook.py · PostToolUse hook（jiacong-flow plugin 安装即启用）

用途（两层）：
    1. **记录**：在 AI 用 Edit / Write 修改 card.md / scratch.md 后追加 flow-log 事件
    2. **守门**：违纪信号以 stderr 提示 AI（PostToolUse 无法回滚，仅作下一轮反馈）

第四组件边界：template.md 也进入提醒范围，但不写 flow-log 事件；hook 只提示运行 check_units.py，核心机制仍在 init_project.py / topic_new.py / card_write.py。

触发条件（hook 内部自判，避免误触发）：
    - tool 是 Edit / Write
    - 目标文件是 card.md 或 scratch.md
    - 目标文件位于 <项目根>/topics/NNN_简称/ 目录

只记录显式信号：
    - card.md frontmatter 的 status / parent 字段变更
    - scratch.md frontmatter 的 status 字段变更
    - scratch.md 新出现的 → card §N 标记

违纪检测（stderr 警告；非阻塞）：
    - 编辑 card.md / scratch.md 但 flow-log 无 `created` 事件 → "应先跑 topic_new.py"
    - 直接 Edit/Write card.md → 提醒优先走 `card_write.py` 结构化写入前门

不做推断。不捕获 tool 是否成功（这个由 Claude Code 传给 hook）。

Tokens 成本：
    hook 仅读 md 文件 + 写 flow-log.jsonl，不注入 context 到 AI 对话。
    stderr 警告是唯一 context 注入，仅在真违纪时出现，合规路径静默。

CLI 用法（测试）：
    echo '{"tool_name":"Edit","tool_input":{"file_path":"/path/to/topics/001_x/card.md"}}' \
        | python flow_hook.py --event-json
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.journal import (  # noqa: E402
    get_events,
    log_card_status,
    log_link,
    log_migrate,
    log_parent_change,
    log_scratch_status,
)
from _lib.data import parse_card_text  # noqa: E402
from _lib.guard import (  # noqa: E402
    check_card_structure,
    fix_card,
    fix_scratch,
    fix_root_field,
    warn_only,
)


_CARD_NAME = "card.md"
_SCRATCH_NAME = "scratch.md"
_TEMPLATE_NAME = "template.md"
_TOPIC_RE = re.compile(r"topics[/\\](\d{3}_[^/\\]+)[/\\]")
_TOOL_NAME_MAP = {
    "Edit": "Edit",
    "Write": "Write",
    "edit": "Edit",
    "replace": "Edit",
    "edit_file": "Edit",
    "modify_file": "Edit",
    "write_file": "Write",
}


def _parse_frontmatter(text: str) -> dict:
    """最小化 YAML frontmatter 解析：仅一级字段。"""
    if not text.startswith("---"):
        return {}
    lines = text.split("\n")
    fm: dict = {}
    for i in range(1, len(lines)):
        ln = lines[i].rstrip()
        if ln == "---":
            break
        if ":" not in ln:
            continue
        k, _, v = ln.partition(":")
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def _status_emoji(status_str: str) -> str:
    """从 '⏳ 进行中' 取首个 emoji。"""
    if not status_str:
        return ""
    parts = status_str.strip().split()
    return parts[0] if parts else ""


def _is_confirmed_project_root(path: Path) -> bool:
    marker = path / ".jiacong" / "project.json"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if data.get("confirmed_root") is False:
        return False
    declared = data.get("project_root") or data.get("root")
    if isinstance(declared, str) and declared.strip():
        declared_path = Path(declared)
        if not declared_path.is_absolute():
            declared_path = path / declared_path
        try:
            return declared_path.resolve() == path.resolve()
        except Exception:
            return False
    return True


def _find_project_root(path: Path) -> Path | None:
    """从文件路径回溯找项目根；.jiacong/project.json 是授权源，.claude 仅为旧项目 fallback。"""
    p = path.resolve()
    for ancestor in p.parents:
        if _is_confirmed_project_root(ancestor):
            return ancestor
        if (ancestor / ".claude").is_dir():
            return ancestor
    return None


def _extract_topic(path: Path) -> str | None:
    """从路径里提取 NNN_简称。"""
    m = _TOPIC_RE.search(str(path))
    return m.group(1) if m else None


def _find_workspace_root(project_root: Path) -> Path | None:
    """从项目根回溯识别外层 workspace 容器。"""
    for ancestor in (project_root, *project_root.parents):
        try:
            if not (ancestor / ".repo.git").exists():
                continue
            if (ancestor / "main").is_dir() or (ancestor / "worktrees").is_dir():
                return ancestor
        except Exception:
            continue
    return None


def _git_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _touch_kind(path: Path, topic: str | None) -> str:
    if path.name == _CARD_NAME:
        return "card"
    if path.name == _SCRATCH_NAME:
        return "scratch"
    if path.name == _TEMPLATE_NAME:
        return "template"
    return "topic-other" if topic else "other"


def _record_touched_file(path: Path, root: Path, tool_name: str) -> None:
    """记录本轮实际触达的项目根/话题，供 Stop 做跨分支 scratch 闭环判断。"""
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
    except Exception:
        return

    topic = _extract_topic(resolved_path)
    topic_id = topic.split("_", 1)[0] if topic and "_" in topic else (topic or "")
    record = {
        "ts": datetime.now().isoformat(timespec="microseconds"),
        "tool_name": tool_name,
        "file_path": str(resolved_path),
        "project_root": str(resolved_root),
        "branch": _git_branch(resolved_root),
        "topic_slug": topic or "",
        "topic_id": topic_id,
        "kind": _touch_kind(resolved_path, topic),
    }

    targets = [resolved_root / ".jiacong" / "round_touched.jsonl"]
    workspace = _find_workspace_root(resolved_root)
    if workspace is not None:
        targets.append(workspace / ".jiacong-workspace" / "round_touched.jsonl")

    line = json.dumps(record, ensure_ascii=False)
    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            continue


def _check_violations(root: Path, topic: str, tool_name: str, name: str) -> None:
    """违纪检测：stderr 警告，不阻塞（PostToolUse 无法回滚）。

    当前最小可执行规则：
        - card.md / scratch.md 被 Edit/Write，但 flow-log 无 `created` 事件
        → 意味着话题绕过了 topic_new.py，frontmatter 很可能漏字段
        - card.md 被 Edit/Write
        → 意味着绕过了 card_write.py 的 section/mode/approval 结构化写入语义
    """
    created = get_events(root, topic=topic, event_type="created")
    if not created:
        msg = (
            f"[flow_hook] ⚠️ 违纪信号：topic={topic} 的 {name} 被 {tool_name}，"
            f"但 flow-log 无 'created' 事件。\n"
            f"[flow_hook]   应先跑：python <skill>/scripts/topic_new.py "
            f"<项目根> <简称> --parent <ID|null> --root <emoji标签>\n"
            f"[flow_hook]   若是从旧项目迁来，手动补：python <skill>/scripts/_lib/flow.py "
            f"<项目根>  后在 .claude/flow-log.jsonl 追加 created 事件。"
        )
        print(msg, file=sys.stderr)

    if name == _CARD_NAME and tool_name in ("Edit", "Write", "Manual"):
        short_id = topic.split("_", 1)[0] if "_" in topic else topic
        msg = (
            f"[flow_hook] ⚠️ card 直接写入提醒（topic={topic}）：{tool_name} 已绕过 card_write.py。\n"
            f"[flow_hook]   card.md 的结构源是 frontmatter toc，正文 📑 本卡目录只读渲染。\n"
            f"[flow_hook]   常规写入请走：python <skill>/scripts/card_write.py "
            f"<项目根> {short_id} --section <N> --mode integrate|replace --content-file <path>\n"
            f"[flow_hook]   结构变更先走：--mode restructure --approval pending，经用户批准后再 approved。"
        )
        print(msg, file=sys.stderr)


def _check_card_structure(topic: str, text: str) -> None:
    """card.md 结构校验：TOC 缺失 / 条数不齐 / 文本错位 → stderr warn。

    违 SKILL.md §2.1 话题（结构优先 + 禁止追加式堆放）。hook 只报 warn 级不报 info。
    """
    toc, sections = parse_card_text(text)
    warns = warn_only(check_card_structure(toc, sections))
    if not warns:
        return
    short_id = topic.split("_", 1)[0] if "_" in topic else topic
    lines = [f"[flow_hook] ⚠️ card 结构警告（topic={topic}）："]
    for w in warns:
        lines.append(f"[flow_hook]   - {w['code']}: {w['msg']}")
    lines.append("[flow_hook]   违 SKILL.md §2.1 话题（结构优先 + 禁止追加式堆放）。")
    lines.append(
        f"[flow_hook]   修复：python <skill>/scripts/check_structure.py <项目根> --card {short_id}"
    )
    print("\n".join(lines), file=sys.stderr)


def handle_edit(file_path: str, tool_name: str = "Edit") -> int:
    """处理一次 Edit/Write 事件。返回 0 表示正常（hook 成功）。"""
    path = Path(file_path)
    if not path.exists():
        return 0

    root = _find_project_root(path)
    if root is None:
        return 0

    _record_touched_file(path, root, tool_name)

    name = path.name
    if name not in (_CARD_NAME, _SCRATCH_NAME, _TEMPLATE_NAME):
        return 0

    topic = _extract_topic(path)
    if not topic:
        return 0

    # template.md 第四组件：只提醒，不写 flow-log，不自动修复
    if name == _TEMPLATE_NAME:
        short_id = topic.split("_", 1)[0] if "_" in topic else topic
        print(
            f"[flow_hook] ⚠️ template.md 直接写入提醒（topic={topic}）：{tool_name} 已修改第四组件。\n"
            f"[flow_hook]   template.md 是建构说明和 unit 模板，不是 card.md 结论源，也不记录任务状态。\n"
            f"[flow_hook]   改完请跑：python <skill>/scripts/check_units.py <项目根> --card {short_id}\n"
            f"[flow_hook]   地图类单元变更后可跑：python <skill>/scripts/render_maps.py <项目根> --card {short_id}",
            file=sys.stderr,
        )
        return 0

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0

    # 先做违纪检测（读 flow-log），再做自动修复，最后记录事件
    _check_violations(root, topic, tool_name, name)

    # 自动修复：把 AI 手写的不合规文件修正到合规态
    try:
        if name == _CARD_NAME:
            fixes = fix_card(path, root)
            root_fix = fix_root_field(path, root)
            if root_fix:
                fixes.append(root_fix)
            if fixes:
                print(
                    f"[flow_hook] 🔧 card 自动修复（topic={topic}）：{'; '.join(fixes)}",
                    file=sys.stderr,
                )
                text = path.read_text(encoding="utf-8")
        elif name == _SCRATCH_NAME:
            fixes = fix_scratch(path, root)
            root_fix = fix_root_field(path, root)
            if root_fix:
                fixes.append(root_fix)
            if fixes:
                print(
                    f"[flow_hook] 🔧 scratch 自动修复（topic={topic}）：{'; '.join(fixes)}",
                    file=sys.stderr,
                )
                text = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[flow_hook] 自动修复失败：{e}", file=sys.stderr)

    fm = _parse_frontmatter(text)

    # 这里简化实现：每次 Edit 后直接记"当前状态"作为一个事件点
    # （真实的 from/to 需要与上次状态对比；此处用 snapshot 事件）
    if name == _CARD_NAME:
        _check_card_structure(topic, text)
        status = _status_emoji(fm.get("status", ""))
        if status:
            log_card_status(root, topic, from_="?", to=status, source="hook")
        parent = fm.get("parent", "null")
        if parent and parent != "null":
            log_parent_change(root, topic, from_="?", to=parent, source="hook")
        # 扫正文新出现的 [[NNN_简称]] 引用
        body = text.split("---\n", 2)[-1] if text.count("---") >= 2 else text
        for m in re.finditer(r"\[\[(\d{3}_[^\]|]+)\]\]", body):
            log_link(root, topic, to_slug=m.group(1), source="hook")
    elif name == _SCRATCH_NAME:
        status = _status_emoji(fm.get("status", ""))
        if status:
            log_scratch_status(root, topic, from_="?", to=status, source="hook")
        # 扫 → card §N 迁移标记
        body = text.split("---\n", 2)[-1] if text.count("---") >= 2 else text
        for m in re.finditer(r"→\s*card\s*(§[\w.]+)", body):
            log_migrate(root, topic, to_section=f"card {m.group(1)}", source="hook")

    return 0


def _read_event_json() -> dict | None:
    """读取 hook stdin JSON，优先按 bytes 解码，避免 Windows 中文路径被控制台编码污染。"""
    try:
        stream = getattr(sys.stdin, "buffer", None)
        if stream is not None:
            raw_value = stream.read()
            raw = _decode_stdin_bytes(raw_value) if isinstance(raw_value, bytes) else str(raw_value)
        else:
            raw = sys.stdin.read()
    except Exception:
        return None

    if not raw.strip():
        return {}
    try:
        event = json.loads(raw)
        return event if isinstance(event, dict) else None
    except json.JSONDecodeError:
        return None


def _decode_stdin_bytes(value: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", getattr(sys.stdin, "encoding", "") or "", "gbk"):
        if not encoding:
            continue
        try:
            return value.decode(encoding)
        except Exception:
            pass
    return value.decode("utf-8", errors="replace")


def _event_tool_name(event: dict) -> str:
    raw = event.get("tool_name") or event.get("toolName") or event.get("name") or ""
    if not isinstance(raw, str):
        return ""
    return _TOOL_NAME_MAP.get(raw, _TOOL_NAME_MAP.get(raw.lower(), ""))


def _event_file_path(event: dict) -> str:
    tool_input = event.get("tool_input") or event.get("toolInput") or event.get("args") or {}
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "filePath", "path", "absolute_path", "absolutePath"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="flow-log PostToolUse hook（可选）")
    parser.add_argument(
        "--event-json",
        action="store_true",
        help="从 stdin 读取 Claude Code hook 事件 JSON（默认模式）",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="直接指定一个 md 文件（绕过 stdin，方便手动触发 / 批处理）",
    )
    args = parser.parse_args()

    if args.file:
        return handle_edit(args.file, tool_name="Manual")

    # stdin 模式：读 Claude Code / Codex 传入的 hook 事件
    event = _read_event_json()
    if event is None:
        print("[hook] 无效 JSON，跳过", file=sys.stderr)
        return 0
    if not event:
        return 0

    tool_name = _event_tool_name(event)
    if tool_name not in ("Edit", "Write"):
        return 0

    file_path = _event_file_path(event)
    if not file_path:
        return 0

    return handle_edit(file_path, tool_name=tool_name)


if __name__ == "__main__":
    sys.exit(main())
