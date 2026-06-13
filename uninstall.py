# -*- coding: utf-8 -*-
"""
uninstall.py · jiacong-flow 的多 CLI 入口干净卸载

用途：
    移除 install.py 注入的 marker 块，保留用户手工写的所有其他内容。

幂等：
    - marker 块不存在 → 无动作
    - marker 块存在 → 删除 marker 之间（含 marker 自身）的内容

用法：
    python uninstall.py                  # 默认从 ~/.claude/CLAUDE.md 卸载
    python uninstall.py --agent codex    # 从 ~/.codex/AGENTS.md、~/.codex/skills、~/.codex/hooks.json 触发器卸载
    python uninstall.py --agent gemini   # 从 ~/.gemini/GEMINI.md、~/.gemini/skills、~/.gemini/settings.json 卸载
    python uninstall.py --agent hermes   # 从 ~/.hermes/SOUL.md 和 ~/.hermes/plugins/jiacong-flow 卸载
    python uninstall.py --agent all      # 从所有已支持 CLI 卸载
    python uninstall.py --target <path>
    python uninstall.py --dry-run        # 只报告不改文件
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
MARKERS_PATH = PLUGIN_ROOT / "protocol-fragments" / "markers.json"

TRIGGER_DEST = Path.home() / ".claude" / "hooks" / "jiacong_flow_trigger.py"
TRIGGER_MARKER = "jiacong_flow_trigger"
JIACONG_MARKER = "jiacong-flow"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def _load_markers() -> dict:
    with open(MARKERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _configure_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


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


def _remove_block(text: str, marker_begin: str, marker_end: str) -> tuple[str, bool]:
    """删除 marker 块（含前后可能的分隔线/空行）；返回 (new_text, removed?)"""
    begin_re = re.compile(re.escape(marker_begin.split(" v")[0]) + r".*?-->")
    m = begin_re.search(text)
    if not m:
        return text, False
    start = m.start()
    end_pos = text.find(marker_end, m.end())
    if end_pos == -1:
        return text, False
    block_end = end_pos + len(marker_end)

    # 向前吞掉紧邻的 "\n\n---\n\n"（append_eof 时会加）和多余空行
    before = text[:start]
    after = text[block_end:]
    # 清理 before 末尾的分隔与空行
    before = re.sub(r"\n*(---\n+)?\s*$", "\n", before)
    # 清理 after 开头的空行
    after = re.sub(r"^\s*\n", "", after)
    return before + after, True


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


def _remove_cli_skill(
    dest: Path,
    dry_run: bool = False,
    source: Path | None = None,
) -> tuple[str, bool, bool]:
    source = source or PLUGIN_ROOT / "skills" / "smarter-project"
    if not (dest.exists() or dest.is_symlink()):
        return "not present", False, True
    if dest.is_symlink() and _same_path(dest, source):
        if dry_run:
            return "remove symlink", True, True
        dest.unlink()
        return "removed symlink", True, True
    if dest.is_dir() and not dest.is_symlink() and _same_tree(dest, source):
        if dry_run:
            return "remove copy", True, True
        shutil.rmtree(dest)
        return "removed copy", True, True
    return "skipped(existing skill target differs)", False, False


def _remove_cli_skills(
    agent_id: str,
    skills_dir: Path,
    dry_run: bool = False,
) -> list[tuple[str, str, bool, bool]]:
    """移除本插件安装的所有并列 skill。"""
    sources = _skill_sources()
    if not sources:
        return [(f"{agent_id}_skills", "not present", False, True)]

    reports: list[tuple[str, str, bool, bool]] = []
    for source in sources:
        action, removed, ok = _remove_cli_skill(
            skills_dir / source.name,
            dry_run=dry_run,
            source=source,
        )
        reports.append((f"{agent_id}_skill_{source.name}", action, removed, ok))
    return reports


def _uninstall_trigger(dry_run: bool = False) -> list[tuple[str, str]]:
    """移除用户级触发器脚本和 settings.json 中的 hook 注册。"""
    report: list[tuple[str, str]] = []

    # 1. 删除触发器脚本
    if TRIGGER_DEST.is_file():
        if dry_run:
            report.append(("trigger_script", "remove"))
        else:
            TRIGGER_DEST.unlink()
            report.append(("trigger_script", "removed"))
    else:
        report.append(("trigger_script", "not present"))

    # 2. 从 settings.json 移除 hook
    if not SETTINGS_PATH.is_file():
        report.append(("trigger_hook", "not present"))
        return report

    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        report.append(("trigger_hook", "not present"))
        return report

    hooks = settings.get("hooks", {})
    changed = False
    for event in list(hooks.keys()):
        original_len = len(hooks[event])
        hooks[event] = [
            group
            for group in hooks[event]
            if not _is_claude_bootstrap_group(group)
        ]
        if len(hooks[event]) < original_len:
            changed = True
        if not hooks[event]:
            del hooks[event]

    if changed:
        if dry_run:
            report.append(("trigger_hook", "remove"))
        else:
            settings["hooks"] = hooks
            SETTINGS_PATH.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            report.append(("trigger_hook", "removed"))
    else:
        report.append(("trigger_hook", "not present"))

    return report


def _is_claude_bootstrap_group(group: dict) -> bool:
    for hook in group.get("hooks", []):
        command = hook.get("command", "").replace("\\", "/")
        if TRIGGER_MARKER in command:
            return True
        if _is_agent_bootstrap_command(command, "claude"):
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


def _uninstall_project_hooks(project_root: Path | None, dry_run: bool = False) -> list[tuple[str, str]]:
    """从项目级 settings.local.json 移除 jiacong-flow hooks。"""
    report: list[tuple[str, str]] = []
    if project_root is None:
        return report

    settings_path = project_root / ".claude" / "settings.local.json"
    if not settings_path.is_file():
        return report

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return report

    hooks = settings.get("hooks", {})
    changed = False
    for event in list(hooks.keys()):
        original_len = len(hooks[event])
        hooks[event] = [
            group
            for group in hooks[event]
            if not any(
                JIACONG_MARKER in h.get("command", "")
                for h in group.get("hooks", [])
            )
        ]
        if len(hooks[event]) < original_len:
            changed = True
        if not hooks[event]:
            del hooks[event]

    if changed:
        if dry_run:
            report.append(("project_hooks", "remove"))
        else:
            settings["hooks"] = hooks
            settings_path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            report.append(("project_hooks", "removed"))

    return report


def _is_jiacong_hook_group(group: dict) -> bool:
    plugin_root_text = str(PLUGIN_ROOT).replace("\\", "/")
    for hook in group.get("hooks", []):
        command = hook.get("command", "").replace("\\", "/")
        if JIACONG_MARKER in command or plugin_root_text in command:
            return True
    return False


def _uninstall_codex_hooks(
    hooks_path: Path = DEFAULT_CODEX_HOOKS_PATH,
    dry_run: bool = False,
) -> list[tuple[str, str]]:
    """Remove jiacong-flow user-level hook groups from Codex hooks.json."""
    return _uninstall_cli_hooks("codex", hooks_path, dry_run)


def _uninstall_gemini_hooks(
    hooks_path: Path = DEFAULT_GEMINI_HOOKS_PATH,
    dry_run: bool = False,
) -> list[tuple[str, str]]:
    """Remove jiacong-flow user-level hook groups from Gemini settings.json."""
    return _uninstall_cli_hooks("gemini", hooks_path, dry_run)


def _uninstall_cli_hooks(
    agent_id: str,
    hooks_path: Path,
    dry_run: bool = False,
) -> list[tuple[str, str]]:
    report: list[tuple[str, str]] = []
    if not hooks_path.is_file():
        return [(f"{agent_id}_hooks", "not present")]

    try:
        settings = json.loads(hooks_path.read_text(encoding="utf-8"))
    except Exception:
        return [(f"{agent_id}_hooks", "not present")]

    hooks = settings.get("hooks", {})
    changed = False
    for event in list(hooks.keys()):
        original_len = len(hooks[event])
        hooks[event] = [
            group for group in hooks[event] if not _is_jiacong_hook_group(group)
        ]
        if len(hooks[event]) < original_len:
            changed = True
            report.append((f"{agent_id}_hook_{event}", "remove" if dry_run else "removed"))
        if not hooks[event]:
            del hooks[event]

    if changed and not dry_run:
        settings["hooks"] = hooks
        _backup(hooks_path)
        hooks_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if not changed:
        report.append((f"{agent_id}_hooks", "not present"))
    return report


def uninstall_claude(target: Path, dry_run: bool = False) -> int:
    _configure_stdout()
    if not target.exists():
        print(f"[info] 目标文件不存在：{target}")
        trigger_report = _uninstall_trigger(dry_run=dry_run)
        for tid, taction in trigger_report:
            icon = "✅" if "removed" in taction else "—"
            print(f"  {icon} {tid}: {taction}")
        try:
            project_root = Path.cwd().resolve()
        except Exception:
            project_root = None
        project_report = _uninstall_project_hooks(project_root, dry_run=dry_run)
        for pid, paction in project_report:
            icon = "✅" if "removed" in paction else "—"
            print(f"  {icon} {pid}: {paction}")
        return 0

    markers = _load_markers()
    text = target.read_text(encoding="utf-8")
    original = text
    report: list[tuple[str, bool]] = []

    for frag in markers["fragments"]:
        text, removed = _remove_block(text, frag["marker_begin"], frag["marker_end"])
        report.append((frag["id"], removed))

    if text == original:
        print("[info] 无可卸载的 marker 块（已是干净状态）")
        _print_claude_hook_cleanup(dry_run=dry_run)
        return 0

    if dry_run:
        print("[dry-run] 将要移除以下 marker 块：")
        for fid, removed in report:
            if removed:
                print(f"  - {fid}")
        _print_claude_hook_cleanup(dry_run=dry_run)
        return 0

    bak = _backup(target)
    target.write_text(text, encoding="utf-8")

    print(f"[ok] 已卸载 {target}")
    print(f"     备份：{bak}")
    for fid, removed in report:
        icon = "✅" if removed else "—"
        print(f"  {icon} {fid}: {'removed' if removed else 'not present'}")

    _print_claude_hook_cleanup(dry_run=dry_run)
    return 0


def _print_claude_hook_cleanup(dry_run: bool = False) -> None:
    trigger_report = _uninstall_trigger(dry_run=dry_run)
    for tid, taction in trigger_report:
        icon = "✅" if "removed" in taction else "—"
        print(f"  {icon} {tid}: {taction}")

    try:
        project_root = Path.cwd().resolve()
    except Exception:
        project_root = None
    project_report = _uninstall_project_hooks(project_root, dry_run=dry_run)
    for pid, paction in project_report:
        icon = "✅" if "removed" in paction else "—"
        print(f"  {icon} {pid}: {paction}")


def _uninstall_instruction_agent(
    agent_id: str,
    label: str,
    target: Path,
    marker_begin: str,
    marker_end: str,
    skills_dir: Path,
    entry_report_id: str,
    dry_run: bool = False,
    remove_skill: bool = True,
) -> int:
    _configure_stdout()
    if not target.exists():
        print(f"[info] {label} 入口文件不存在：{target}")
        if remove_skill:
            skill_reports = _remove_cli_skills(
                agent_id,
                skills_dir,
                dry_run=dry_run,
            )
            skills_ok = all(ok for _skill_id, _action, _removed, ok in skill_reports)
            for skill_id, skill_action, _skill_removed, skill_ok in skill_reports:
                icon = "✅" if skill_ok else "⚠️"
                print(f"  {icon} {skill_id}: {skill_action}")
            return 0 if skills_ok else 1
        return 0

    text = target.read_text(encoding="utf-8")
    original = text
    text, removed_entry = _remove_block(text, marker_begin, marker_end)

    skill_reports: list[tuple[str, str, bool, bool]] = []
    if remove_skill:
        skill_reports = _remove_cli_skills(agent_id, skills_dir, dry_run=dry_run)
    skills_removed = any(removed for _skill_id, _action, removed, _ok in skill_reports)
    skills_ok = all(ok for _skill_id, _action, _removed, ok in skill_reports)

    if text == original and not skills_removed:
        print(f"[info] {label} 入口无可卸载内容")
        if remove_skill:
            for skill_id, skill_action, _skill_removed, skill_ok in skill_reports:
                icon = "✅" if skill_ok else "⚠️"
                print(f"  {icon} {skill_id}: {skill_action}")
        if dry_run:
            return 0
        return 0 if skills_ok else 1

    if dry_run:
        print(f"[dry-run] {label} 卸载将要发生以下变更：")
        if removed_entry:
            print(f"  - {entry_report_id}")
        if remove_skill:
            for skill_id, skill_action, _skill_removed, _skill_ok in skill_reports:
                print(f"  - {skill_id}: {skill_action}")
        return 0

    if text != original:
        bak = _backup(target)
        target.write_text(text, encoding="utf-8")
        print(f"[ok] 已卸载 {target}")
        print(f"     备份：{bak}")
        print(f"  ✅ {entry_report_id}: removed")
    else:
        print(f"[info] {label} 入口文件无 marker 块")

    if remove_skill:
        for skill_id, skill_action, _skill_removed, skill_ok in skill_reports:
            icon = "✅" if skill_ok else "⚠️"
            print(f"  {icon} {skill_id}: {skill_action}")
    return 0 if skills_ok else 1


def uninstall_codex(target: Path, dry_run: bool = False, remove_skill: bool = True) -> int:
    rc = _uninstall_instruction_agent(
        agent_id="codex",
        label="Codex",
        target=target,
        marker_begin=CODEX_MARKER_BEGIN,
        marker_end=CODEX_MARKER_END,
        skills_dir=DEFAULT_CODEX_SKILLS_DIR,
        entry_report_id="codex_agents",
        dry_run=dry_run,
        remove_skill=remove_skill,
    )
    if target == DEFAULT_CODEX_TARGET:
        hook_report = _uninstall_codex_hooks(dry_run=dry_run)
        for hook_id, hook_action in hook_report:
            icon = "✅" if "removed" in hook_action or hook_action == "remove" else "—"
            print(f"  {icon} {hook_id}: {hook_action}")
    return rc


def uninstall_gemini(target: Path, dry_run: bool = False, remove_skill: bool = True) -> int:
    rc = _uninstall_instruction_agent(
        agent_id="gemini",
        label="Gemini CLI",
        target=target,
        marker_begin=GEMINI_MARKER_BEGIN,
        marker_end=GEMINI_MARKER_END,
        skills_dir=DEFAULT_GEMINI_SKILLS_DIR,
        entry_report_id="gemini_context",
        dry_run=dry_run,
        remove_skill=remove_skill,
    )
    if target == DEFAULT_GEMINI_TARGET:
        hook_report = _uninstall_gemini_hooks(dry_run=dry_run)
        for hook_id, hook_action in hook_report:
            icon = "✅" if "removed" in hook_action or hook_action == "remove" else "—"
            print(f"  {icon} {hook_id}: {hook_action}")
    return rc


def uninstall_hermes(target: Path, dry_run: bool = False) -> int:
    _configure_stdout()
    text_changed = False
    if target.exists():
        text = target.read_text(encoding="utf-8")
        new_text, removed = _remove_block(text, HERMES_MARKER_BEGIN, HERMES_MARKER_END)
        text_changed = new_text != text
    else:
        new_text = ""
        removed = False
        print(f"[info] Hermes SOUL.md 不存在：{target}")

    plugin_dest = DEFAULT_HERMES_PLUGINS_DIR / "jiacong-flow"
    plugin_action = "not present"
    plugin_ok = True
    if plugin_dest.is_symlink():
        try:
            points_to_current = plugin_dest.resolve() == HERMES_PLUGIN_SOURCE.resolve()
        except OSError:
            points_to_current = False
        if points_to_current:
            plugin_action = "remove symlink" if dry_run else "removed symlink"
            if not dry_run:
                plugin_dest.unlink()
        else:
            plugin_action = f"skipped symlink to other target: {plugin_dest.resolve()}"
            plugin_ok = False
    elif plugin_dest.exists():
        plugin_action = "skipped existing directory; remove manually"
        plugin_ok = False

    if dry_run:
        print("[dry-run] Hermes 卸载将要发生以下变更：")
        print(f"  - hermes_soul: {'remove marker' if removed else 'not present'}")
        print(f"  - hermes_plugin: {plugin_action}")
        return 0 if plugin_ok else 1

    if text_changed:
        bak = _backup(target)
        target.write_text(new_text, encoding="utf-8")
        print(f"[ok] 已卸载 {target}")
        print(f"     备份：{bak}")
        print("  ✅ hermes_soul: removed")
    elif target.exists():
        print("[info] Hermes SOUL.md 无可卸载 marker 块")

    icon = "✅" if plugin_ok else "⚠️"
    print(f"  {icon} hermes_plugin: {plugin_action}")
    return 0 if plugin_ok else 1


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


def _uninstall_agent(agent_id: str, target: Path, args: argparse.Namespace) -> int:
    if agent_id == "claude":
        return uninstall_claude(target, dry_run=args.dry_run)
    if agent_id == "codex":
        return uninstall_codex(target, dry_run=args.dry_run, remove_skill=not args.keep_skill)
    if agent_id == "gemini":
        return uninstall_gemini(target, dry_run=args.dry_run, remove_skill=not args.keep_skill)
    if agent_id == "hermes":
        return uninstall_hermes(target, dry_run=args.dry_run)
    raise ValueError(agent_id)


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="jiacong-flow · 多 CLI 入口卸载器")
    parser.add_argument(
        "--agent",
        default="claude",
        help="卸载目标：claude、codex、gemini、hermes、all，或逗号组合如 claude,codex；默认 claude",
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
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--keep-skill",
        action="store_true",
        help="Codex/Gemini 卸载时保留对应 skills/<skill-name>",
    )
    args = parser.parse_args(argv)

    if args.list_agents:
        print("支持的 CLI 目标：")
        print("  - claude  -> ~/.claude/CLAUDE.md + Claude Code fragments/hooks")
        print("  - codex   -> ~/.codex/AGENTS.md + ~/.codex/skills/<skill-name> + ~/.codex/hooks.json trigger")
        print("  - gemini  -> ~/.gemini/GEMINI.md + ~/.gemini/skills/<skill-name> + ~/.gemini/settings.json")
        print("  - hermes  -> ~/.hermes/SOUL.md + ~/.hermes/plugins/jiacong-flow")
        print("  - all     -> 同时卸载以上全部目标")
        return 0

    try:
        agents = _parse_agents(args.agent)
    except ValueError as exc:
        parser.error(str(exc))

    if args.target is not None and len(agents) != 1:
        parser.error("--target 只能和单个 --agent 搭配；多 CLI 卸载请使用默认目标路径")

    exit_code = 0
    for index, agent_id in enumerate(agents):
        if len(agents) > 1:
            if index:
                print("")
            print(f"== {agent_id} ==")
        target = args.target or _default_target(agent_id)
        rc = _uninstall_agent(agent_id, target, args)
        exit_code = max(exit_code, rc)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
