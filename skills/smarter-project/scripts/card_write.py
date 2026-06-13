# -*- coding: utf-8 -*-
"""
card_write.py · card.md 结构化写入通道

用法：
    python card_write.py <项目根> <NNN|NNN_简称> [--section <N>] [--mode <integrate|replace|restructure>]
        [--content-file <path>] [--approval pending|approved]
    python card_write.py <项目根> <NNN|NNN_简称> --unit <unit_key|unit_name>
        [--section <N>] [--unit-title <名称>] [--unit-index <编号>]

三种 mode：
    integrate   — 向已有 §N 融入内容（section 必须存在于 frontmatter toc）
    replace     — 整段重写 §N（同 integrate 前置条件，但替换原有内容）
    restructure — 新增/改/删 section（需 --approval approved 或写入 pending 标记）

执行流程：
    1. 读 card.md，解析 frontmatter toc 字段
    2. 验证 --section N 是否在 toc 中
    3. 从 stdin 或 --content-file 读取新内容
    4. 定位正文 §N 区域，按 mode 写入
    5. 重新渲染 📑 本卡目录区（frontmatter → 正文只读视图）
    6. 跑 check_card_structure 验证
    7. 记录 edit 事件到 .jiacong/cache/card-edits.jsonl

设计原则：
    - frontmatter toc 是唯一结构源，正文 📑 区是只读渲染
    - integrate 模式 stderr 输出 section intent 作为语义锚
    - 合规路径（走本脚本）静默；违规路径（直接 Edit）由 flow_hook 强警告
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.guard import check_card_structure  # noqa: E402

try:
    import frontmatter as _fm  # type: ignore
    _HAS_FM = True
except ImportError:
    _HAS_FM = False


# --------------------------------------------------------------------------- #
# frontmatter 读写
# --------------------------------------------------------------------------- #

def _load_card(card_path: Path) -> tuple[dict, str, str]:
    """返回 (metadata_dict, body_str, raw_text)。"""
    raw = card_path.read_text(encoding="utf-8")
    if _HAS_FM:
        post = _fm.loads(raw)
        return dict(post.metadata), post.content, raw
    # 降级
    if not raw.startswith("---"):
        return {}, raw, raw
    lines = raw.split("\n")
    end = -1
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            end = i
            break
    if end == -1:
        return {}, raw, raw
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return {}, raw, raw
    fm = yaml.safe_load("\n".join(lines[1:end])) or {}
    body = "\n".join(lines[end + 1:])
    return fm, body, raw


def _normalize_surrogates(text: str) -> str:
    """合并 surrogate pair，避免含 emoji 的 YAML 写回时触发编码错误。"""
    if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        return text
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def _normalize_surrogate_values(value):
    """递归清洗 metadata/body 中的 surrogate pair。"""
    if isinstance(value, str):
        return _normalize_surrogates(value)
    if isinstance(value, list):
        return [_normalize_surrogate_values(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_surrogate_values(item) for item in value)
    if isinstance(value, dict):
        return {
            _normalize_surrogate_values(key): _normalize_surrogate_values(item)
            for key, item in value.items()
        }
    return value


def _save_card(card_path: Path, fm: dict, body: str) -> None:
    """写回 card.md：frontmatter + body。"""
    fm = _normalize_surrogate_values(fm)
    body = _normalize_surrogates(body)
    if _HAS_FM:
        import io
        post = _fm.Post(body, **fm)
        # python-frontmatter 默认 handler
        out = _normalize_surrogates(_fm.dumps(post, allow_unicode=True))
        card_path.write_text(out, encoding="utf-8")
        return
    # 降级
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        print("[错误] python-frontmatter 和 PyYAML 均不可用，无法写入 card.md", file=__import__("sys").stderr)
        return
    fm_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).rstrip()
    card_path.write_text(_normalize_surrogates(f"---\n{fm_str}\n---\n{body}"), encoding="utf-8")


# --------------------------------------------------------------------------- #
# TOC 解析（从 frontmatter toc 字段）
# --------------------------------------------------------------------------- #

_TOC_RE = re.compile(r'^"?(\d+(?:\.\d+)*)\s+(.+?)(?:\s*\|\s*(.+?))?"?$')


def parse_toc_entry(entry: str) -> dict:
    """解析 '1.2 标题 | intent' 格式。"""
    m = _TOC_RE.match(entry.strip())
    if not m:
        return {"num": "", "title": entry.strip(), "intent": "", "level": 1}
    num = m.group(1)
    title = m.group(2).strip()
    intent = (m.group(3) or "").strip()
    level = num.count(".") + 1
    return {"num": num, "title": title, "intent": intent, "level": level}


def parse_toc(toc_list: list[str]) -> list[dict]:
    """解析 frontmatter toc 列表。"""
    return [parse_toc_entry(e) for e in toc_list]


def find_section(toc: list[dict], section_num: str) -> dict | None:
    """按编号查找 toc 条目。"""
    for t in toc:
        if t["num"] == section_num:
            return t
    return None


# --------------------------------------------------------------------------- #
# 正文 section 定位与写入
# --------------------------------------------------------------------------- #

_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")


def _locate_section(body: str, section_num: str) -> tuple[int, int] | None:
    """定位 §N 在 body 中的行范围 [start, end)。"""
    lines = body.split("\n")
    start = None
    level = None
    for i, ln in enumerate(lines):
        m = _HEADING_RE.match(ln)
        if not m:
            continue
        h_level = len(m.group(1))
        heading = m.group(2).strip()
        # 匹配 "N 标题" 或 "N.M 标题"
        if re.match(rf"^{re.escape(section_num)}\s+", heading):
            start = i
            level = h_level
            continue
        if start is not None and h_level <= level:
            return (start, i)
    if start is not None:
        return (start, len(lines))
    return None


def _render_toc_view(toc: list[dict]) -> str:
    """从 toc 列表渲染 📑 只读视图。"""
    lines = []
    for t in toc:
        indent = "  " * (t["level"] - 1)
        intent_part = f" — *{t['intent']}*" if t["intent"] else ""
        lines.append(f"{indent}- {t['num']} {t['title']}{intent_part}")
    return "\n".join(lines)


def _update_toc_view(body: str, toc: list[dict]) -> str:
    """替换正文中 📑 本卡目录区为最新渲染。"""
    lines = body.split("\n")
    toc_start = None
    toc_end = None
    in_toc = False

    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if re.match(r"^##\s*📑\s*本卡目录", stripped):
            toc_start = i
            in_toc = True
            continue
        if in_toc:
            if stripped == "---" or (stripped.startswith("## ") and "📑" not in stripped):
                toc_end = i
                break
    if toc_start is None:
        return body

    if toc_end is None:
        toc_end = len(lines)

    new_toc = [
        lines[toc_start],  # ## 📑 本卡目录
        "",
        "<!-- ⚠️ 本区由 card_write.py 自动渲染，勿直接编辑。源：frontmatter toc 字段 -->",
        "",
        _render_toc_view(toc),
        "",
    ]

    return "\n".join(lines[:toc_start] + new_toc + lines[toc_end:])


# --------------------------------------------------------------------------- #
# template.md 单元读取
# --------------------------------------------------------------------------- #

_UNIT_BLOCK_RE = re.compile(
    r"<!--\s*unit:(?P<key>[^\s]+)\s+section:(?P<section>[^\s]*)\s+name:(?P<name>.*?)\s*-->\n"
    r"(?P<body>.*?)\n<!--\s*/unit\s*-->",
    re.DOTALL,
)


def _load_units(template_path: Path) -> list[dict]:
    """读取 template.md 中的 unit 块。"""
    if not template_path.exists():
        return []
    text = template_path.read_text(encoding="utf-8")
    units: list[dict] = []
    for m in _UNIT_BLOCK_RE.finditer(text):
        units.append({
            "key": m.group("key").strip(),
            "section": m.group("section").strip(),
            "name": m.group("name").strip(),
            "body": m.group("body").strip(),
        })
    return units


def _find_unit(units: list[dict], query: str) -> dict | None:
    """按 key 或 name 查找 unit。"""
    for unit in units:
        if query == unit["key"] or query == unit["name"]:
            return unit
    return None


_TITLE_PLACEHOLDERS = (
    "<对象名>", "<模块名>", "<变量名>", "<模型名>",
    "<节点名>", "<规则名>", "<名称>", "<任务名>",
)


def _instantiate_unit(unit: dict, unit_title: str | None, unit_index: str | None) -> str:
    """把 unit 模板替换成可写入 card.md 的实例。"""
    text = unit["body"]
    title = unit_title or "（待定）"
    index = unit_index or "n"
    for ph in _TITLE_PLACEHOLDERS:
        text = text.replace(ph, title)
    text = text.replace("T{n}", f"T{index}")
    return text


# --------------------------------------------------------------------------- #
# edit 日志
# --------------------------------------------------------------------------- #

def _log_edit(root: Path, topic: str, section: str, mode: str) -> None:
    """追加到 .jiacong/cache/card-edits.jsonl。"""
    log_path = root / ".jiacong" / "cache" / "card-edits.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "topic": topic,
        "section": section,
        "mode": mode,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="card.md 结构化写入通道。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("card", help="话题 NNN 或 NNN_简称")
    parser.add_argument("--section", default=None, help="章节编号（如 1, 2, 1.1）")
    parser.add_argument("--mode", default="integrate", choices=["integrate", "replace", "restructure"])
    parser.add_argument("--unit", default=None, help="从 template.md 实例化 unit key/name")
    parser.add_argument("--unit-title", default=None, help="unit 实例标题，替换 <对象名>/<任务名> 等占位")
    parser.add_argument("--unit-index", default=None, help="Trace 等编号型 unit 的序号，替换 T{n}")
    parser.add_argument("--content-file", default=None, help="内容来源文件（否则从 stdin）")
    parser.add_argument("--approval", default=None, choices=["pending", "approved"],
                        help="restructure 模式的审批状态")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    topics_dir = root / "topics"

    # 定位 card.md
    card_path = None
    for d in sorted(topics_dir.iterdir()) if topics_dir.exists() else []:
        if not d.is_dir():
            continue
        short = d.name.split("_", 1)[0]
        if args.card == d.name or args.card == short:
            cp = d / "card.md"
            if cp.exists():
                card_path = cp
                break
    if card_path is None:
        print(f"[错误] 未找到 card：{args.card}", file=sys.stderr)
        return 1

    topic_slug = card_path.parent.name
    fm, body, _ = _load_card(card_path)
    toc_raw = fm.get("toc", [])
    if not toc_raw:
        print("[错误] frontmatter 无 toc 字段", file=sys.stderr)
        return 1
    toc = parse_toc(toc_raw)

    content_from_unit: str | None = None
    if args.unit:
        units = _load_units(card_path.parent / "template.md")
        if not units:
            print("[错误] 当前话题没有 template.md unit 块", file=sys.stderr)
            return 1
        unit = _find_unit(units, args.unit)
        if unit is None:
            available = [f"{u['key']}({u['name']})" for u in units]
            print(f"[错误] 未找到 unit：{args.unit}。可用：{available}", file=sys.stderr)
            return 1
        if args.section is None:
            args.section = unit.get("section") or None
        if args.section is None:
            print("[错误] unit 未声明 section，请显式传 --section", file=sys.stderr)
            return 1
        content_from_unit = _instantiate_unit(unit, args.unit_title, args.unit_index)
        print(f"[unit] 使用 {unit['key']}（{unit['name']}）→ §{args.section}", file=sys.stderr)
    elif args.section is None:
        print("[错误] 非 unit 写入必须传 --section", file=sys.stderr)
        return 1

    # restructure 模式
    if args.mode == "restructure":
        if args.approval != "approved":
            fm.setdefault("toc_pending", [])
            print(f"[pending] restructure 需要用户审批。", file=sys.stderr)
            print(f"[pending] 当前 toc: {toc_raw}", file=sys.stderr)
            print(f"[pending] 请用户确认后重跑 --approval approved", file=sys.stderr)
            return 2
        # approved：此处由 AI 传入新 toc 内容（通过 stdin 或 content-file）
        print(f"[ok] restructure approved，请更新 frontmatter toc 后重跑 integrate", file=sys.stderr)
        _log_edit(root, topic_slug, args.section, "restructure")
        return 0

    # integrate / replace：验证 section 存在于 toc
    entry = find_section(toc, args.section)
    if entry is None:
        nums = [t["num"] for t in toc]
        print(f"[错误] §{args.section} 不在 toc 中。可用：{nums}", file=sys.stderr)
        print(f"[提示] 需新增章节请用 --mode restructure --approval pending", file=sys.stderr)
        return 1

    # 输出 intent 语义锚
    if entry["intent"]:
        print(f"[intent] §{args.section}（{entry['title']}）：{entry['intent']}", file=sys.stderr)
        print(f"[intent] 请确认写入内容属于此 intent。", file=sys.stderr)

    # 读取内容
    if content_from_unit is not None:
        content = content_from_unit
    elif args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()
    if not content.strip():
        print("[错误] 写入内容为空", file=sys.stderr)
        return 1

    # 定位 section 并写入
    loc = _locate_section(body, args.section)
    if loc is None:
        print(f"[错误] 正文中未找到 §{args.section} 标题", file=sys.stderr)
        return 1

    start, end = loc
    lines = body.split("\n")
    heading_line = lines[start]

    if args.mode == "replace":
        new_section = [heading_line, "", content.rstrip(), ""]
    else:  # integrate
        existing = lines[start + 1:end]
        # 去掉尾部空行
        while existing and not existing[-1].strip():
            existing.pop()
        existing.append("")
        existing.append(content.rstrip())
        existing.append("")
        new_section = [heading_line] + existing

    new_body = "\n".join(lines[:start] + new_section + lines[end:])

    # 渲染 📑 本卡目录
    new_body = _update_toc_view(new_body, toc)

    # 更新 frontmatter updated
    fm["updated"] = datetime.now().strftime("%Y-%m-%d")

    # 写回
    _save_card(card_path, fm, new_body)

    # 校验
    from _lib.topics_loader import parse_md
    data = parse_md(card_path)
    issues = check_card_structure(data["toc"], data["sections"])
    if issues:
        print(f"[warn] 写入后结构校验发现问题：", file=sys.stderr)
        for it in issues:
            print(f"  - {it['code']}: {it['msg']}", file=sys.stderr)
    else:
        print(f"[ok] §{args.section} 写入完成，结构校验通过")

    _log_edit(root, topic_slug, args.section, args.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
