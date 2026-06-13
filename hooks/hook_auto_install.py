# -*- coding: utf-8 -*-
"""
用户级 SessionStart 触发器。

安装到 CLI 的用户级 hooks 配置中。每次会话启动时检测当前项目是否
需要 jiacong-flow hooks：
  1. `.jiacong/project.json` 或项目入口存在 → 继续
  2. 项目级 hooks 已有 jiacong-flow hooks → 跳过
  3. 安装 hooks 到项目级配置 + 首轮焦点/流水检查
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.agents import normalized_agent
from lib.debug import hook_debug
from lib.events import event_cwd, read_hook_event, setup_encoding
from lib.messages import msg
from lib.output import write_context
from lib.roots import RootResolution, resolve_roots

MARKER = "jiacong-flow"


def _setup_encoding() -> None:
    setup_encoding()


_messages: list[str] = []


def _emit(msg: str) -> None:
    """收集消息，最后统一以 JSON 协议输出。"""
    _messages.append(msg)


def _flush_output(event_name: str = "SessionStart") -> None:
    """将收集的消息以 hookSpecificOutput JSON 协议写入 stdout。"""
    write_context(normalized_agent(), event_name, _messages)


def _read_hook_event() -> dict:
    return read_hook_event()


def _find_project_root() -> Path | None:
    return resolve_roots().project_root


def _resolve_roots() -> RootResolution:
    return resolve_roots()


def _has_project_marker(project_root: Path) -> bool:
    return (project_root / ".jiacong" / "project.json").is_file()


def _has_claude_md(project_root: Path) -> bool:
    return (
        (project_root / ".claude" / "CLAUDE.md").is_file()
        or (project_root / "CLAUDE.md").is_file()
    )


def _has_project_entry(project_root: Path) -> bool:
    return (
        _has_project_marker(project_root)
        or (project_root / "AGENTS.md").is_file()
        or (project_root / "GEMINI.md").is_file()
        or _has_claude_md(project_root)
    )


def _jiacong_flow_install_path(plugin_root: str = "") -> Path | None:
    if plugin_root:
        try:
            path = Path(plugin_root).expanduser().resolve()
            if path.is_dir():
                return path
        except Exception:
            pass

    installed = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(installed.read_text(encoding="utf-8"))
        for key, entries in data.get("plugins", {}).items():
            if MARKER in key and entries:
                path = Path(entries[0]["installPath"])
                if path.is_dir():
                    return path
    except Exception:
        pass
    return None


def _project_hooks_path(project_root: Path, agent: str) -> Path:
    if agent == "codex":
        return project_root / ".codex" / "hooks.json"
    if agent == "gemini":
        return project_root / ".gemini" / "settings.json"
    return project_root / ".claude" / "settings.local.json"


def _active_worktree_hint(workspace_root: Path, install_path: Path) -> str:
    return msg(
        "auto.workspace_no_selection",
        marker=MARKER,
        switch_script=install_path / "workspace_use.py",
        workspace_root=workspace_root,
    )


def _candidate_init_hint(candidate_root: Path, install_path: Path) -> str:
    return msg(
        "auto.candidate_init",
        marker=MARKER,
        init_script=install_path / "skills" / "smarter-project" / "scripts" / "init_project.py",
        candidate_root=candidate_root,
    )


def _has_jiacong_hooks(settings_path: Path) -> bool:
    if not settings_path.is_file():
        return False
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        for groups in data.get("hooks", {}).values():
            for group in groups:
                for hook in group.get("hooks", []):
                    if MARKER in hook.get("command", ""):
                        return True
    except Exception:
        pass
    return False


def _is_jiacong_group(group: dict) -> bool:
    for hook in group.get("hooks", []):
        if MARKER in hook.get("command", ""):
            return True
    return False


def _hook_commands(data: dict, event: str) -> set[str]:
    commands: set[str] = set()
    for group in data.get("hooks", {}).get(event, []):
        for hook in group.get("hooks", []):
            command = hook.get("command", "")
            if command:
                commands.add(command)
    return commands


def _has_current_jiacong_hooks(
    settings_path: Path,
    install_path: Path,
    agent: str,
) -> bool:
    if not settings_path.is_file():
        return False
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    expected = _build_hooks(install_path, agent)
    expected_commands: dict[str, set[str]] = {}
    for event, groups in expected.items():
        expected_commands[event] = set()
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if command:
                    expected_commands[event].add(command)

    for event, groups in data.get("hooks", {}).items():
        for group in groups:
            if not _is_jiacong_group(group):
                continue
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if command not in expected_commands.get(event, set()):
                    return False

    for event, groups in expected.items():
        actual = _hook_commands(data, event)
        for group in groups:
            for hook in group.get("hooks", []):
                if hook.get("command", "") not in actual:
                    return False
    return True


def _hook_python_for(script: str | Path, executable: str | None = None) -> str:
    script_text = str(script).replace("\\", "/")
    executable_text = str(executable or sys.executable).replace("\\", "/")
    executable_lower = executable_text.lower()
    is_posix_script = script_text.startswith("/")
    is_windows_python = ":/" in executable_text or executable_lower.endswith("python.exe")
    if is_posix_script and is_windows_python:
        return "python3"
    return executable_text


def _build_hooks(install_path: Path, agent: str = "claude") -> dict:
    hooks_dir = str(install_path / "hooks").replace("\\", "/")
    flow_script = str(
        install_path / "skills" / "smarter-project" / "scripts" / "flow_hook.py"
    ).replace("\\", "/")

    def _arg(value: str) -> str:
        if any(ch.isspace() for ch in value) or '"' in value:
            return '"' + value.replace('"', '\\"') + '"'
        return value

    def _cmd(script: str, extra: str = "") -> str:
        suffix = f" {extra}" if extra else ""
        python = _hook_python_for(script)
        if agent in ("codex", "gemini"):
            return f"{_arg(python)} {_arg(script)}{suffix}"
        return f'{_arg(python)} {_arg(script)}{suffix}'

    agent_extra = f"--agent {agent}" if agent in ("codex", "gemini") else ""

    if agent == "gemini":
        return {
            "SessionStart": [
                {
                    "matcher": "startup",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd(
                                f"{hooks_dir}/hook_session_start.py",
                                agent_extra,
                            ),
                            "timeout": 15,
                        }
                    ],
                }
            ],
            "BeforeAgent": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd(
                                f"{hooks_dir}/hook_user_prompt.py",
                                agent_extra,
                            ),
                            "timeout": 10,
                        }
                    ],
                }
            ],
            "AfterTool": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd(flow_script, "--event-json"),
                            "timeout": 10,
                        }
                    ],
                }
            ],
            "AfterAgent": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd(f"{hooks_dir}/hook_stop.py", agent_extra),
                            "timeout": 10,
                        }
                    ],
                }
            ],
            "SessionEnd": [
                {
                    "matcher": "exit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd(f"{hooks_dir}/hook_session_end.py", agent_extra),
                            "timeout": 15,
                        }
                    ],
                }
            ],
        }

    hooks = {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(
                            f"{hooks_dir}/hook_session_start.py",
                            agent_extra,
                        ),
                        "timeout": 15,
                    }
                ]
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(
                            f"{hooks_dir}/hook_user_prompt.py",
                            agent_extra,
                        ),
                        "timeout": 10,
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(flow_script, "--event-json"),
                        "timeout": 10,
                    }
                ],
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(f"{hooks_dir}/hook_stop.py", agent_extra),
                        "timeout": 10,
                    }
                ]
            }
        ],
    }

    if agent != "codex":
        hooks["SessionEnd"] = [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _cmd(f"{hooks_dir}/hook_session_end.py"),
                        "timeout": 15,
                    }
                ]
            }
        ]

    return hooks


def _install_hooks(
    project_root: Path,
    install_path: Path,
    agent: str = "claude",
) -> bool:
    settings_path = _project_hooks_path(project_root, agent)
    existing: dict = {}
    if settings_path.is_file():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    if agent == "claude" and "version" not in existing:
        existing["version"] = 1

    hooks = existing.setdefault("hooks", {})
    for event in list(hooks.keys()):
        hooks[event] = [
            group for group in hooks[event] if not _is_jiacong_group(group)
        ]
        if not hooks[event]:
            del hooks[event]

    for event, groups in _build_hooks(install_path, agent).items():
        hooks.setdefault(event, []).extend(groups)

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def _run_first_checks(project_root: Path, install_path: Path) -> None:
    skill_dir = install_path / "skills" / "smarter-project"

    focus_path = project_root / ".claude" / "focus"
    try:
        focus_value = (
            focus_path.read_text(encoding="utf-8").strip()
            if focus_path.is_file()
            else ""
        )
    except Exception:
        focus_value = ""

    if not focus_value:
        _emit(msg("auto.focus_missing"))
        _emit(
            msg(
                "auto.focus_new",
                topic_new_script=skill_dir / "scripts" / "topic_new.py",
                project_root=project_root,
            )
        )

    stream_path = project_root / "logs" / "stream.md"
    if not stream_path.is_file():
        _emit(msg("auto.stream_missing"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--agent", choices=("claude", "codex", "gemini"), default="claude")
    parser.add_argument("--plugin-root", default="")
    return parser.parse_known_args(argv)[0]


def main() -> None:
    hook_root: Path | None = None
    project_root: Path | None = None
    try:
        _setup_encoding()
        args = _parse_args()
        hook_event = _read_hook_event()
        roots = resolve_roots(event_cwd(hook_event))
        hook_root = roots.hook_root
        project_root = roots.project_root
        hook_debug(
            "SessionStart:auto_install",
            "start",
            hook_root=hook_root,
            details={
                "agent": args.agent,
                "root_kind": roots.kind,
                "plugin_root": args.plugin_root,
            },
        )
        install_path = _jiacong_flow_install_path(args.plugin_root)
        if not install_path:
            return

        hook_root = roots.hook_root
        if hook_root is None:
            return

        if project_root is None:
            if roots.workspace_root is not None and hook_root == roots.workspace_root:
                if not _has_current_jiacong_hooks(
                    _project_hooks_path(hook_root, args.agent),
                    install_path,
                    args.agent,
                ):
                    _install_hooks(hook_root, install_path, args.agent)
            # 用户级 SessionStart 只负责自动安装与事实缓存；未确认根默认静默。
            # 建档/项目治理意图出现时，由 UserPromptSubmit 输出风险边界。
            return

        if not _has_project_entry(project_root):
            return

        if _has_current_jiacong_hooks(
            _project_hooks_path(hook_root, args.agent),
            install_path,
            args.agent,
        ):
            return
        if _install_hooks(hook_root, install_path, args.agent):
            if args.agent == "codex":
                _emit(
                    msg(
                        "auto.install_codex",
                        marker=MARKER,
                        hooks_path=_project_hooks_path(hook_root, args.agent),
                    )
                )
            else:
                _emit(
                    msg(
                        "auto.install_default",
                        marker=MARKER,
                        hooks_path=_project_hooks_path(hook_root, args.agent),
                    )
                )
            _run_first_checks(project_root, install_path)
    except Exception as exc:
        hook_debug(
            "SessionStart:auto_install",
            "exception",
            project_root=project_root,
            hook_root=hook_root,
            exc=exc,
        )
        pass
    finally:
        hook_debug(
            "SessionStart:auto_install",
            "exit",
            project_root=project_root,
            hook_root=hook_root,
            details={"messages": len(_messages)},
        )
        _flush_output()
        sys.exit(0)


if __name__ == "__main__":
    main()
