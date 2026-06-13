# -*- coding: utf-8 -*-
"""
install.py · jiacong-flow 的多 CLI 入口注入器

用途：
    Claude Code 模式：把 protocol-fragments/ 里的八块内容按 markers.json
    配置插入用户级 CLAUDE.md。
    Codex 模式：把 jiacong-flow 入口写入用户级 AGENTS.md，安装
    skills/ 下的并列 skill 入口，并注册 Codex 用户级触发器。
    Gemini CLI 模式：把 jiacong-flow 入口写入用户级 GEMINI.md，安装
    skills/ 下的并列 skill 目录，并注册 Gemini 用户级 bootstrap hook。
    Hermes 模式：把八块 fragment 拼合写入用户级 SOUL.md（marker 包裹），
    把自包含插件链接到 ~/.hermes/plugins/jiacong-flow；旧 skill symlink 会被清理，
    hooks 由 plugin.yaml 声明。

幂等：
    - 已存在的 marker 块 → 替换内容（更新）
    - 不存在 → 按 insert_after_section / insert_after_line_match / append_eof 插入
    - 手工改 marker **外** 内容不受影响

用法：
    python install.py                           # 默认装到 ~/.claude/CLAUDE.md
    python install.py --agent codex             # 装到 ~/.codex/AGENTS.md + ~/.codex/skills/ + ~/.codex/hooks.json 触发器
    python install.py --agent gemini            # 装到 ~/.gemini/GEMINI.md + ~/.gemini/skills/ + ~/.gemini/settings.json
    python install.py --agent hermes            # 装到 ~/.hermes/SOUL.md + ~/.hermes/skills/（无 hook 注册）
    python install.py --agent claude,codex      # 同时安装多个 CLI
    python install.py --agent all               # 安装全部已支持 CLI
    python install.py --target <path>           # 指定目标文件
    python install.py --dry-run                 # 只报告不改文件

卸载见 uninstall.py。
"""
from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_CLAUDE_TARGET = Path.home() / ".claude" / "CLAUDE.md"
DEFAULT_CODEX_TARGET = Path.home() / ".codex" / "AGENTS.md"
DEFAULT_CODEX_SKILLS_DIR = Path.home() / ".codex" / "skills"
DEFAULT_CODEX_HOOKS_PATH = Path.home() / ".codex" / "hooks.json"
DEFAULT_GEMINI_TARGET = Path.home() / ".gemini" / "GEMINI.md"
DEFAULT_GEMINI_SKILLS_DIR = Path.home() / ".gemini" / "skills"
DEFAULT_GEMINI_HOOKS_PATH = Path.home() / ".gemini" / "settings.json"
DEFAULT_HERMES_SOUL = Path.home() / ".hermes" / "SOUL.md"
DEFAULT_HERMES_SKILLS_DIR = Path.home() / ".hermes" / "skills"
DEFAULT_HERMES_PLUGINS_DIR = Path.home() / ".hermes" / "plugins"
CODEX_MARKER_BEGIN = "<!-- JC:CODEX_GLOBAL:BEGIN v1.1 -->"
CODEX_MARKER_END = "<!-- JC:CODEX_GLOBAL:END -->"
GEMINI_MARKER_BEGIN = "<!-- JC:GEMINI_GLOBAL:BEGIN v1.0 -->"
GEMINI_MARKER_END = "<!-- JC:GEMINI_GLOBAL:END -->"
HERMES_MARKER_BEGIN = "<!-- JC:FRAGMENTS:BEGIN v1.5 -->"
HERMES_MARKER_END = "<!-- JC:FRAGMENTS:END -->"
SUPPORTED_AGENTS = ("claude", "codex", "gemini", "hermes")
PLUGIN_ROOT = Path(__file__).parent
HERMES_PLUGIN_SOURCE = PLUGIN_ROOT / "hermes-plugin"
FRAGMENTS_DIR = PLUGIN_ROOT / "protocol-fragments"
MARKERS_PATH = FRAGMENTS_DIR / "markers.json"

TRIGGER_SOURCE = PLUGIN_ROOT / "hooks" / "hook_auto_install.py"
TRIGGER_DEST = Path.home() / ".claude" / "hooks" / "jiacong_flow_trigger.py"
TRIGGER_MARKER = "jiacong_flow_trigger"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
JIACONG_HOOK_MARKER = "jiacong-flow"


def _load_markers() -> dict:
    with open(MARKERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _configure_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _load_fragment(file_name: str) -> str:
    path = FRAGMENTS_DIR / file_name
    return path.read_text(encoding="utf-8").rstrip() + "\n"


def _backup(target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = target.with_name(f"{target.name}.{stamp}.bak")
    if bak.exists():
        for i in range(2, 1000):
            candidate = target.with_name(f"{target.name}.{stamp}.{i}.bak")
            if not candidate.exists():
                bak = candidate
                break
    shutil.copy2(target, bak)
    return bak


def _find_marker_block(text: str, marker_begin: str, marker_end: str) -> tuple[int, int] | None:
    """找 marker 块在 text 里的起止字符位置；不存在返回 None。"""
    begin_re = re.compile(re.escape(marker_begin.split(" v")[0]) + r".*?-->")
    m = begin_re.search(text)
    if not m:
        return None
    start = m.start()
    end_pos = text.find(marker_end, m.end())
    if end_pos == -1:
        return None
    return (start, end_pos + len(marker_end))


def _insert_fragment(text: str, frag: dict, content: str) -> tuple[str, str]:
    """
    按 frag 配置把 content 插入 text。
    返回 (new_text, action) where action ∈ {"update","inserted","appended","warning"}
    """
    marker_begin = frag["marker_begin"]
    marker_end = frag["marker_end"]
    wrapped = f"{marker_begin}\n{content.rstrip()}\n{marker_end}"

    # 1) 已有 marker → 替换
    block = _find_marker_block(text, marker_begin, marker_end)
    if block:
        start, end = block
        return text[:start] + wrapped + text[end:], "update"

    # 2) append_eof
    if frag.get("insert_mode") == "append_eof":
        tail = "\n\n---\n\n" + wrapped + "\n"
        return text.rstrip() + tail, "appended"

    # 3) insert_after_section（section 头后插入一个空行再插）
    after_section = frag.get("insert_after_section")
    if after_section:
        # 找该 section 标题行，插在该 section 全部内容结束（下一个同级 # 前）
        lines = text.split("\n")
        idx = -1
        for i, ln in enumerate(lines):
            if ln.strip() == after_section.strip():
                idx = i
                break
        if idx == -1:
            return text, "warning"
        # 找该 section 结束（下一个 # 开头且同级或更高；这里简化：下一个 "# " 开头）
        end_idx = len(lines)
        for j in range(idx + 1, len(lines)):
            if lines[j].startswith("# "):
                end_idx = j
                break
        insertion = "\n" + wrapped + "\n"
        new_lines = lines[:end_idx] + [insertion] + lines[end_idx:]
        return "\n".join(new_lines), "inserted"

    # 4) insert_after_line_match（匹配一行关键词后，after_paragraph = 找下一个空行再插）
    after_line = frag.get("insert_after_line_match")
    if after_line:
        lines = text.split("\n")
        idx = -1
        for i, ln in enumerate(lines):
            if after_line in ln:
                idx = i
                break
        if idx == -1:
            return text, "warning"
        if frag.get("insert_mode") == "after_paragraph":
            # 找下一个空行作为段落结束
            end_idx = len(lines)
            for j in range(idx + 1, len(lines)):
                if lines[j].strip() == "":
                    end_idx = j
                    break
            insertion_lines = [""] + wrapped.split("\n")
            new_lines = lines[: end_idx] + insertion_lines + lines[end_idx:]
            return "\n".join(new_lines), "inserted"
        else:
            # 直接在匹配行后插
            insertion_lines = [""] + wrapped.split("\n") + [""]
            new_lines = lines[: idx + 1] + insertion_lines + lines[idx + 1 :]
            return "\n".join(new_lines), "inserted"

    return text, "warning"


def _codex_entry() -> str:
    return """# jiacong-flow · Codex 全局入口

@./skills/smarter-project/SKILL.md

- Codex 全局上下文使用 `$CODEX_HOME/AGENTS.md`；本入口只写用户级默认规则。
- 项目根存在 `AGENTS.md` 时，它是 canonical 项目入口；Codex 原生读取并遵循该文件。
- `CLAUDE.md`、`GEMINI.md`、`HERMES.md` 是其他 CLI 的项目级 adapter，均应回到 `AGENTS.md`。
- `.claude/CLAUDE.md` 只作为旧项目 legacy fallback；不得把它当作新项目的 canonical 入口。
- `skills/` 下所有并列 skill 同步安装到 `$CODEX_HOME/skills/<skill-name>`，供 Codex 原生 skills 发现；上方 `@` 导入 `smarter-project` 作为项目管理兼容桥。
- 涉及项目初始化、话题体系、流水、焦点切换、角色库、文档结构时，默认启用 `smarter-project` skill。
- 涉及复杂提案、架构、方法论、决策支持、研究综述、证据治理或 skill/plugin/agent 设计时，默认启用 `one-turn-proposal` skill；处于项目内时，持久化写入仍回到 `smarter-project`。
- Claude Code 协议注入使用 `python install.py --agent claude`；Codex 全局入口使用 `python install.py --agent codex`；多 CLI 同步使用 `python install.py --agent claude,codex` 或 `--agent all`。
"""


def _gemini_entry() -> str:
    return """# jiacong-flow · Gemini CLI 全局入口

@./skills/smarter-project/SKILL.md
@./skills/one-turn-proposal/SKILL.md

- Gemini CLI 全局上下文使用 `~/.gemini/GEMINI.md`，并支持 `@file.md` 导入；本入口通过导入并列 skill 入口复用项目管理与复杂提案能力。
- 项目根存在 `AGENTS.md` 时，它是 canonical 项目入口；项目级 `GEMINI.md` 是 Gemini adapter，应指向并服从 `AGENTS.md`。
- `.claude/CLAUDE.md` 只作为旧项目 legacy fallback；不得把它当作新项目的 canonical 入口。
- `skills/` 下所有并列 skill 同步安装到 `~/.gemini/skills/<skill-name>`；Gemini hook runtime 使用 `~/.gemini/settings.json` 与项目级 `.gemini/settings.json`，事件映射为 `BeforeAgent`/`AfterTool`/`AfterAgent`。
- 涉及项目初始化、话题体系、流水、焦点切换、角色库、文档结构时，默认启用 `smarter-project` 工作流。
- 涉及复杂提案、架构、方法论、决策支持、研究综述、证据治理或 skill/plugin/agent 设计时，默认启用 `one-turn-proposal` 工作流；处于项目内时，持久化写入仍回到 `smarter-project`。
- Gemini CLI 全局入口使用 `python install.py --agent gemini`；多 CLI 同步使用 `python install.py --agent claude,codex,gemini` 或 `--agent all`。
"""


def _upsert_marked_entry(
    text: str,
    marker_begin: str,
    marker_end: str,
    content: str,
) -> tuple[str, str]:
    wrapped = f"{marker_begin}\n{content.rstrip()}\n{marker_end}"
    block = _find_marker_block(text, marker_begin, marker_end)
    if block:
        start, end = block
        return text[:start] + wrapped + text[end:], "update"
    tail = "\n\n---\n\n" + wrapped + "\n"
    return text.rstrip() + tail, "appended"


def _path_label(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _same_tree(left: Path, right: Path) -> bool:
    if not left.is_dir() or not right.is_dir():
        return False
    left_files = sorted(
        path.relative_to(left)
        for path in left.rglob("*")
        if path.is_file()
    )
    right_files = sorted(
        path.relative_to(right)
        for path in right.rglob("*")
        if path.is_file()
    )
    if left_files != right_files:
        return False
    return all(
        filecmp.cmp(left / rel, right / rel, shallow=False)
        for rel in left_files
    )


def _skill_sources() -> list[Path]:
    skills_root = PLUGIN_ROOT / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(
        path
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    )


def _install_cli_skill(
    agent_id: str,
    dest: Path,
    skill_mode: str,
    replace_skill: bool,
    dry_run: bool,
    source: Path | None = None,
    report_id: str | None = None,
) -> tuple[str, str, bool]:
    """
    安装 CLI 可复用的单个 skill 入口目录。
    返回 (id, action, ok)；存在冲突且未允许替换时 ok=False。
    """
    source = source or PLUGIN_ROOT / "skills" / "smarter-project"
    report_id = report_id or f"{agent_id}_skill"
    if skill_mode == "none":
        return report_id, "skipped", True

    if not source.exists():
        return report_id, f"warning(source missing: {source})", False

    dest_exists = dest.exists() or dest.is_symlink()
    if dest_exists:
        if dest.is_symlink() and _same_path(dest, source):
            return report_id, "current", True
        if dest.is_dir() and not dest.is_symlink() and _same_tree(dest, source):
            return report_id, "current", True
        if not replace_skill:
            target = ""
            if dest.is_symlink():
                target = f" -> {_path_label(dest)}"
            return report_id, f"warning(existing skill{target}; use --replace-skill)", False
        if dry_run:
            return report_id, f"replace_{skill_mode}", True
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    if dry_run:
        return report_id, f"install_{skill_mode}", True

    dest.parent.mkdir(parents=True, exist_ok=True)
    if skill_mode == "copy":
        shutil.copytree(source, dest)
        return report_id, "copied", True

    try:
        dest.symlink_to(source, target_is_directory=True)
    except OSError as exc:
        return report_id, f"warning(symlink failed: {exc}; retry with --skill-mode copy)", False
    return report_id, "linked", True


def _install_cli_skills(
    agent_id: str,
    skills_dir: Path,
    skill_mode: str,
    replace_skill: bool,
    dry_run: bool,
) -> list[tuple[str, str, bool]]:
    """安装 skills/ 下所有并列 skill。"""
    if skill_mode == "none":
        return [(f"{agent_id}_skills", "skipped", True)]

    sources = _skill_sources()
    if not sources:
        return [(f"{agent_id}_skills", "warning(no skills found)", False)]

    reports: list[tuple[str, str, bool]] = []
    for source in sources:
        reports.append(
            _install_cli_skill(
                agent_id=agent_id,
                dest=skills_dir / source.name,
                skill_mode=skill_mode,
                replace_skill=replace_skill,
                dry_run=dry_run,
                source=source,
                report_id=f"{agent_id}_skill_{source.name}",
            )
        )
    return reports


def _install_trigger(dry_run: bool = False) -> list[tuple[str, str]]:
    """Register Claude's user-level bootstrap hook.

    The bootstrap imports sibling modules from ``hooks/lib``. It must therefore
    run from the plugin root instead of a standalone copied trigger file.
    """
    report: list[tuple[str, str]] = []

    if not TRIGGER_SOURCE.is_file():
        report.append(("trigger_script", f"warning(source missing: {TRIGGER_SOURCE})"))
        return report

    report.append(("trigger_script", "plugin-root"))

    trigger_cmd = _hook_command(
        TRIGGER_SOURCE,
        "--agent",
        "claude",
        "--plugin-root",
        str(PLUGIN_ROOT),
    )

    settings: dict = {}
    if SETTINGS_PATH.is_file():
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            settings = {}

    hooks = settings.setdefault("hooks", {})
    session_hooks = hooks.setdefault("SessionStart", [])

    changed = False
    current = False
    migrated = False
    kept_groups: list[dict] = []

    for group in session_hooks:
        if _is_claude_bootstrap_group(group):
            if _group_has_command(group, trigger_cmd):
                current = True
                kept_groups.append(group)
            else:
                changed = True
                migrated = True
            continue
        kept_groups.append(group)

    if changed and not dry_run:
        hooks["SessionStart"] = kept_groups

    if current:
        report.append(("trigger_hook", "current"))
    elif dry_run:
        report.append(("trigger_hook", "migrate" if migrated else "register"))
    else:
        hooks.setdefault("SessionStart", []).append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": trigger_cmd,
                        "timeout": 15,
                    }
                ]
            }
        )
        changed = True
        report.append(("trigger_hook", "migrated" if migrated else "registered"))

    if changed and not dry_run:
        SETTINGS_PATH.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return report


def _is_claude_bootstrap_group(group: dict) -> bool:
    for hook in group.get("hooks", []):
        command = hook.get("command", "").replace("\\", "/")
        if TRIGGER_MARKER in command:
            return True
        if _is_agent_bootstrap_command(command, "claude"):
            return True
    return False


def _group_has_command(group: dict, command: str) -> bool:
    return any(hook.get("command", "") == command for hook in group.get("hooks", []))


def _group_has_any_command(group: dict, commands: set[str]) -> bool:
    return any(hook.get("command", "") in commands for hook in group.get("hooks", []))


def _hook_group_commands(groups: list[dict]) -> set[str]:
    return {
        hook.get("command", "")
        for group in groups
        for hook in group.get("hooks", [])
        if hook.get("command", "")
    }


def _quote_hook_arg(value: str | Path) -> str:
    text = str(value).replace("\\", "/")
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or '"' in text:
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _hook_python_for(script: str | Path, executable: str | None = None) -> str:
    script_text = str(script).replace("\\", "/")
    executable_text = str(executable or sys.executable).replace("\\", "/")
    executable_lower = executable_text.lower()
    is_posix_script = script_text.startswith("/")
    is_windows_python = ":/" in executable_text or executable_lower.endswith("python.exe")
    if is_posix_script and is_windows_python:
        return "python3"
    return executable_text


def _hook_command(script: Path, *args: str, executable: str | None = None) -> str:
    parts = [_quote_hook_arg(_hook_python_for(script, executable)), _quote_hook_arg(script)]
    parts.extend(_quote_hook_arg(arg) for arg in args)
    return " ".join(parts)


def _codex_hook_groups() -> dict[str, list[dict]]:
    return _user_bootstrap_hook_groups("codex")


def _gemini_hook_groups() -> dict[str, list[dict]]:
    return _user_bootstrap_hook_groups("gemini")


def _user_bootstrap_hook_groups(agent: str) -> dict[str, list[dict]]:
    hooks_dir = PLUGIN_ROOT / "hooks"
    matcher = "startup|resume" if agent == "codex" else "startup"
    return {
        "SessionStart": [
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": _hook_command(
                            hooks_dir / "hook_auto_install.py",
                            "--agent",
                            agent,
                            "--plugin-root",
                            str(PLUGIN_ROOT),
                        ),
                        "timeout": 15,
                    }
                ],
            }
        ],
    }


def _is_jiacong_hook_group(group: dict) -> bool:
    plugin_root_text = str(PLUGIN_ROOT).replace("\\", "/")
    for hook in group.get("hooks", []):
        command = hook.get("command", "").replace("\\", "/")
        if JIACONG_HOOK_MARKER in command or plugin_root_text in command:
            return True
    return False


def _is_codex_bootstrap_group(group: dict) -> bool:
    return _is_user_bootstrap_group(group, "codex")


def _is_gemini_bootstrap_group(group: dict) -> bool:
    return _is_user_bootstrap_group(group, "gemini")


def _is_user_bootstrap_group(group: dict, agent: str) -> bool:
    for hook in group.get("hooks", []):
        command = hook.get("command", "").replace("\\", "/")
        if _is_agent_bootstrap_command(command, agent):
            return True
    return False


def _is_agent_bootstrap_command(command: str, agent: str) -> bool:
    normalized = command.replace("\\", "/")
    return (
        "hook_auto_install.py" in normalized
        and (
            f"--agent {agent}" in normalized
            or f"--agent={agent}" in normalized
            or f"--agent\" \"{agent}" in normalized
            or f"--agent' '{agent}" in normalized
        )
    )


def _install_codex_hooks(
    hooks_path: Path = DEFAULT_CODEX_HOOKS_PATH,
    dry_run: bool = False,
) -> list[tuple[str, str]]:
    """Register the Codex user-level bootstrap hook."""
    return _install_user_bootstrap_hooks("codex", hooks_path, _codex_hook_groups(), dry_run)


def _install_gemini_hooks(
    hooks_path: Path = DEFAULT_GEMINI_HOOKS_PATH,
    dry_run: bool = False,
) -> list[tuple[str, str]]:
    """Register the Gemini CLI user-level bootstrap hook."""
    return _install_user_bootstrap_hooks("gemini", hooks_path, _gemini_hook_groups(), dry_run)


def _install_user_bootstrap_hooks(
    agent_id: str,
    hooks_path: Path,
    expected: dict[str, list[dict]],
    dry_run: bool = False,
) -> list[tuple[str, str]]:
    report: list[tuple[str, str]] = []
    data: dict = {"hooks": {}}
    if hooks_path.is_file():
        try:
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"hooks": {}}
    hooks = data.setdefault("hooks", {})

    expected_commands = {
        event: _hook_group_commands(groups)
        for event, groups in expected.items()
    }
    changed = False
    migrated_events: set[str] = set()
    current_events: set[str] = set()
    for event in list(hooks.keys()):
        kept_groups: list[dict] = []
        for group in hooks[event]:
            if event == "SessionStart" and _is_user_bootstrap_group(group, agent_id):
                if _group_has_any_command(group, expected_commands.get(event, set())):
                    kept_groups.append(group)
                    current_events.add(event)
                else:
                    changed = True
                    migrated_events.add(event)
                continue
            if _is_jiacong_hook_group(group):
                changed = True
                migrated_events.add(event)
                continue
            kept_groups.append(group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]

    for event, groups in expected.items():
        existing = hooks.setdefault(event, [])
        if event in current_events or any(
            _group_has_any_command(group, expected_commands[event])
            for group in existing
        ):
            report.append((f"{agent_id}_hook_{event}", "current"))
            continue
        report.append(
            (
                f"{agent_id}_hook_{event}",
                "migrate" if event in migrated_events else "register",
            )
        )
        changed = True
        if not dry_run:
            existing.extend(groups)

    if changed and not dry_run:
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        if hooks_path.exists():
            _backup(hooks_path)
        hooks_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return report


def install_claude(target: Path, dry_run: bool = False) -> int:
    _configure_stdout()
    if target.exists():
        text = target.read_text(encoding="utf-8")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        text = ""
        print(f"[info] 目标文件不存在，将创建：{target}")

    markers = _load_markers()
    original = text
    report: list[tuple[str, str]] = []  # (id, action)

    for frag in markers["fragments"]:
        content = _load_fragment(frag["file"])
        text, action = _insert_fragment(text, frag, content)
        report.append((frag["id"], action))

    # Fragment 注入
    if text == original:
        print("[info] Fragment 无变更（所有 marker 块已是最新）")
    elif dry_run:
        print("[dry-run] 将要发生以下变更：")
        for fid, action in report:
            print(f"  - {fid}: {action}")
    else:
        bak = _backup(target)
        target.write_text(text, encoding="utf-8")
        print(f"[ok] 已写入 {target}")
        print(f"     备份：{bak}")
        print(f"     plugin_version: {markers['plugin_version']}")
        for fid, action in report:
            icon = "✅" if action in ("inserted", "update", "appended") else "⚠️"
            print(f"  {icon} {fid}: {action}")

    # 注册用户级触发器（独立于 fragment 变更）
    trigger_report = _install_trigger(dry_run=dry_run)
    for tid, taction in trigger_report:
        icon = "✅" if taction in ("copied", "updated", "registered", "current", "update") else "⚠️"
        print(f"  {icon} {tid}: {taction}")

    return 0


def _install_instruction_agent(
    agent_id: str,
    label: str,
    target: Path,
    default_text: str,
    marker_begin: str,
    marker_end: str,
    entry: str,
    skills_dir: Path,
    entry_report_id: str,
    dry_run: bool = False,
    skill_mode: str = "symlink",
    replace_skill: bool = False,
) -> int:
    _configure_stdout()
    target_exists = target.exists()
    if target_exists:
        text = target.read_text(encoding="utf-8")
    else:
        text = default_text
    original = text

    text, entry_action = _upsert_marked_entry(text, marker_begin, marker_end, entry)
    skill_reports = _install_cli_skills(
        agent_id=agent_id,
        skills_dir=skills_dir,
        skill_mode=skill_mode,
        replace_skill=replace_skill,
        dry_run=dry_run,
    )
    skills_ok = all(ok for _skill_id, _skill_action, ok in skill_reports)

    text_changed = text != original
    if dry_run:
        print(f"[dry-run] {label} 安装将要发生以下变更：")
        print(f"  - {entry_report_id}: {entry_action if text_changed else 'current'}")
        for skill_id, skill_action, _skill_ok in skill_reports:
            print(f"  - {skill_id}: {skill_action}")
        return 0

    if text_changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        bak = _backup(target) if target_exists else None
        target.write_text(text, encoding="utf-8")
        print(f"[ok] 已写入 {target}")
        if bak:
            print(f"     备份：{bak}")
        else:
            print("     备份：新建文件，无备份")
        print(f"  ✅ {entry_report_id}: {entry_action}")
    else:
        print(f"[info] {label} 入口文件无变更（marker 块已是最新）")

    for skill_id, skill_action, skill_ok in skill_reports:
        icon = "✅" if skill_ok else "⚠️"
        print(f"  {icon} {skill_id}: {skill_action}")
    return 0 if skills_ok else 1


def install_codex(
    target: Path,
    dry_run: bool = False,
    skill_mode: str = "symlink",
    replace_skill: bool = False,
) -> int:
    rc = _install_instruction_agent(
        agent_id="codex",
        label="Codex",
        target=target,
        default_text="# Codex Global Instructions\n",
        marker_begin=CODEX_MARKER_BEGIN,
        marker_end=CODEX_MARKER_END,
        entry=_codex_entry(),
        skills_dir=DEFAULT_CODEX_SKILLS_DIR,
        entry_report_id="codex_agents",
        dry_run=dry_run,
        skill_mode=skill_mode,
        replace_skill=replace_skill,
    )
    if target == DEFAULT_CODEX_TARGET:
        hook_report = _install_codex_hooks(dry_run=dry_run)
        for hook_id, hook_action in hook_report:
            icon = "✅" if hook_action in ("current", "register") else "⚠️"
            print(f"  {icon} {hook_id}: {hook_action}")
    return rc


def install_gemini(
    target: Path,
    dry_run: bool = False,
    skill_mode: str = "symlink",
    replace_skill: bool = False,
) -> int:
    rc = _install_instruction_agent(
        agent_id="gemini",
        label="Gemini CLI",
        target=target,
        default_text="# Gemini CLI Global Instructions\n",
        marker_begin=GEMINI_MARKER_BEGIN,
        marker_end=GEMINI_MARKER_END,
        entry=_gemini_entry(),
        skills_dir=DEFAULT_GEMINI_SKILLS_DIR,
        entry_report_id="gemini_context",
        dry_run=dry_run,
        skill_mode=skill_mode,
        replace_skill=replace_skill,
    )
    if target == DEFAULT_GEMINI_TARGET:
        hook_report = _install_gemini_hooks(dry_run=dry_run)
        for hook_id, hook_action in hook_report:
            icon = "✅" if hook_action in ("current", "register") else "⚠️"
            print(f"  {icon} {hook_id}: {hook_action}")
    return rc


def _hermes_entry() -> str:
    """Concatenate all 8 fragments for Hermes SOUL.md marker block."""
    fragments_dir = FRAGMENTS_DIR
    frags = sorted(fragments_dir.glob("*.md"))
    parts: list[str] = []
    for frag in frags:
        parts.append(frag.read_text(encoding="utf-8").rstrip() + "\n")
    return "".join(parts).rstrip()


def install_hermes(
    target: Path,
    dry_run: bool = False,
    skill_mode: str = "none",
    replace_skill: bool = False,
) -> int:
    _configure_stdout()
    entry = _hermes_entry()

    target_exists = target.exists()
    if target_exists:
        text = target.read_text(encoding="utf-8")
    else:
        text = ""
        print(f"[info] 目标文件不存在，将创建：{target}")

    original = text
    text, entry_action = _upsert_marked_entry(
        text, HERMES_MARKER_BEGIN, HERMES_MARKER_END, entry
    )

    # ── Plugin symlink ──────────────────────────────────────────────
    plugin_dest = DEFAULT_HERMES_PLUGINS_DIR / "jiacong-flow"
    plugin_action = "skipped"
    plugin_ok = True
    if HERMES_PLUGIN_SOURCE.is_dir():
        if plugin_dest.is_symlink() or plugin_dest.exists():
            if plugin_dest.is_symlink():
                real_target = plugin_dest.resolve()
                if real_target.resolve() == HERMES_PLUGIN_SOURCE.resolve():
                    plugin_action = "current"
                else:
                    if dry_run:
                        plugin_action = "replace"
                    else:
                        plugin_dest.unlink()
                        plugin_dest.symlink_to(HERMES_PLUGIN_SOURCE, target_is_directory=True)
                        plugin_action = "relinked"
            else:
                # Existing directory (not symlink) — don't overwrite automatically
                plugin_action = "warning(existing directory; remove manually to switch)"
                plugin_ok = False
        else:
            if dry_run:
                plugin_action = "link"
            else:
                plugin_dest.parent.mkdir(parents=True, exist_ok=True)
                plugin_dest.symlink_to(HERMES_PLUGIN_SOURCE, target_is_directory=True)
                plugin_action = "linked"
    else:
        plugin_ok = False
        plugin_action = f"warning(source missing: {HERMES_PLUGIN_SOURCE})"

    # ── Remove old skill symlinks (now served via plugin ctx.register_skill) ──
    old_skill_links = [
        DEFAULT_HERMES_SKILLS_DIR / "smarter-project",
        DEFAULT_HERMES_SKILLS_DIR / "one-turn-proposal",
    ]
    skill_cleanup_reports: list[tuple[str, str, bool]] = []
    for old_link in old_skill_links:
        if old_link.is_symlink():
            real = old_link.resolve()
            if dry_run:
                skill_cleanup_reports.append((f"remove_old_symlink:{old_link.name}", f"would remove -> {real}", True))
            else:
                old_link.unlink()
                skill_cleanup_reports.append((f"remove_old_symlink:{old_link.name}", f"removed -> {real}", True))
        else:
            skill_cleanup_reports.append((f"remove_old_symlink:{old_link.name}", "not_a_symlink/noop", True))

    text_changed = text != original
    if dry_run:
        print("[dry-run] Hermes 安装将要发生以下变更：")
        print(f"  - hermes_soul: {entry_action if text_changed else 'current'}")
        print(f"  - hermes_plugin: {plugin_action}")
        for skill_id, skill_action, _skill_ok in skill_cleanup_reports:
            print(f"  - {skill_id}: {skill_action}")
        print("  - hermes_hooks: Hermes hooks are declared in plugin.yaml — no hook registration needed")
        return 0

    if text_changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        bak = _backup(target) if target_exists else None
        target.write_text(text, encoding="utf-8")
        print(f"[ok] 已写入 {target}")
        if bak:
            print(f"     备份：{bak}")
        else:
            print("     备份：新建文件，无备份")
        print(f"  ✅ hermes_soul: {entry_action}")
    else:
        print("[info] Hermes SOUL.md 入口文件无变更（marker 块已是最新）")

    icon = "✅" if plugin_ok else "⚠️"
    print(f"  {icon} hermes_plugin: {plugin_action}")

    for skill_id, skill_action, skill_ok in skill_cleanup_reports:
        s_icon = "✅" if skill_ok else "⚠️"
        print(f"  {s_icon} {skill_id}: {skill_action}")

    print("  ℹ️ Skills are now registered via plugin ctx.register_skill() — no separate skill symlinks needed")
    print("  ℹ️ Hermes hooks are declared in plugin.yaml — no hook registration needed")
    return 0 if (plugin_ok and all(ok for _, _, ok in skill_cleanup_reports)) else 1


def _parse_agents(raw: str) -> list[str]:
    parts = [part.strip().lower() for part in re.split(r"[, ]+", raw) if part.strip()]
    if not parts:
        raise ValueError("agent 不能为空")
    if "all" in parts:
        if len(parts) > 1:
            raise ValueError("--agent all 不能和其他 agent 混用")
        return list(SUPPORTED_AGENTS)

    invalid = [part for part in parts if part not in SUPPORTED_AGENTS]
    if invalid:
        raise ValueError(
            f"不支持的 agent: {', '.join(invalid)}；可用值：{', '.join(SUPPORTED_AGENTS)}, all"
        )

    selected: list[str] = []
    for part in parts:
        if part not in selected:
            selected.append(part)
    return selected


def _default_target(agent_id: str) -> Path:
    if agent_id == "claude":
        return DEFAULT_CLAUDE_TARGET
    if agent_id == "codex":
        return DEFAULT_CODEX_TARGET
    if agent_id == "gemini":
        return DEFAULT_GEMINI_TARGET
    if agent_id == "hermes":
        return DEFAULT_HERMES_SOUL
    raise ValueError(agent_id)


def _install_agent(agent_id: str, target: Path, args: argparse.Namespace) -> int:
    if agent_id == "claude":
        return install_claude(target, dry_run=args.dry_run)
    if agent_id == "codex":
        return install_codex(
            target,
            dry_run=args.dry_run,
            skill_mode=args.skill_mode,
            replace_skill=args.replace_skill,
        )
    if agent_id == "gemini":
        return install_gemini(
            target,
            dry_run=args.dry_run,
            skill_mode=args.skill_mode,
            replace_skill=args.replace_skill,
        )
    if agent_id == "hermes":
        return install_hermes(
            target,
            dry_run=args.dry_run,
            skill_mode=args.skill_mode,
            replace_skill=args.replace_skill,
        )
    raise ValueError(agent_id)


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="jiacong-flow · 多 CLI 入口注入器")
    parser.add_argument(
        "--agent",
        default="claude",
        help="安装目标：claude、codex、gemini、hermes、all，或逗号组合如 claude,codex；默认 claude",
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="列出当前支持的 CLI 目标后退出",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="目标文件路径；只可与单个 --agent 搭配",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印预期变更，不实际写入",
    )
    parser.add_argument(
        "--skill-mode",
        choices=("symlink", "copy", "none"),
        default="symlink",
        help="Codex/Gemini/Hermes skill 安装方式，默认 symlink",
    )
    parser.add_argument(
        "--replace-skill",
        action="store_true",
        help="Codex/Gemini skill 已存在且目标不同时允许替换",
    )
    args = parser.parse_args(argv)

    if args.list_agents:
        print("支持的 CLI 目标：")
        print("  - claude  -> ~/.claude/CLAUDE.md + Claude Code fragments/hooks")
        print("  - codex   -> ~/.codex/AGENTS.md + ~/.codex/skills/<skill-name> + ~/.codex/hooks.json trigger")
        print("  - gemini  -> ~/.gemini/GEMINI.md + ~/.gemini/skills/<skill-name>")
        print("  - hermes  -> ~/.hermes/SOUL.md + ~/.hermes/plugins/jiacong-flow (plugin handles hooks)")
        print("  - all     -> 同时安装以上全部目标")
        return 0

    try:
        agents = _parse_agents(args.agent)
    except ValueError as exc:
        parser.error(str(exc))

    if args.target is not None and len(agents) != 1:
        parser.error("--target 只能和单个 --agent 搭配；多 CLI 安装请使用默认目标路径")

    exit_code = 0
    for index, agent_id in enumerate(agents):
        if len(agents) > 1:
            if index:
                print("")
            print(f"== {agent_id} ==")
        target = args.target or _default_target(agent_id)
        rc = _install_agent(agent_id, target, args)
        exit_code = max(exit_code, rc)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
