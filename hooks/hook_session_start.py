# -*- coding: utf-8 -*-
"""SessionStart hook: starts watcher and injects startup context."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.agents import normalized_agent
from lib.debug import hook_debug
from lib.events import event_cwd, read_hook_event, setup_encoding
from lib.focus import focus_topic_id, find_topic_dir, last_scratch_header, parse_frontmatter, read_focus
from lib.messages import msg
from lib.output import write_context
from lib.roots import (
    plugin_root,
    resolve_roots,
    script_path,
)


_messages: list[str] = []


def _emit(message: str) -> None:
    _messages.append(message)


def _flush_output(event_name: str = "SessionStart") -> None:
    write_context(normalized_agent(), event_name, _messages)


def _read_pid(pid_path: Path) -> int | None:
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except Exception:
        return None


def _pid_alive_windows(pid: int) -> bool:
    try:
        kernel32 = ctypes.windll.kernel32
        process_query_limited_information = 0x1000
        still_active = 259

        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
        if not handle:
            return False

        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


def _pid_alive_unix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return False


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid)
    return _pid_alive_unix(pid)


def _path_key(path: Path | str) -> str:
    try:
        return str(Path(path).resolve()).casefold()
    except Exception:
        return str(path).casefold()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _script_project_root(path: Path) -> Path | None:
    script = path.resolve()
    try:
        app_root = script.parents[3]
    except IndexError:
        return None
    candidate = app_root.parent
    if (candidate / "topics").is_dir() and (candidate / ".claude").is_dir():
        return candidate
    return None


def _terminate_windows(pid: int) -> None:
    try:
        kernel32 = ctypes.windll.kernel32
        process_terminate = 0x0001
        handle = kernel32.OpenProcess(process_terminate, False, int(pid))
        if not handle:
            return
        try:
            kernel32.TerminateProcess(handle, 0)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        pass


def _terminate_unix(pid: int) -> None:
    try:
        os.kill(pid, 15)
    except Exception:
        pass


def _terminate_pid(pid: int) -> None:
    if os.name == "nt":
        _terminate_windows(pid)
    else:
        _terminate_unix(pid)


def _watcher_metadata_path(project_root: Path) -> Path:
    return project_root / ".claude" / "watcher.json"


def _watcher_is_current(project_root: Path, watcher_script: Path, metadata: dict) -> bool:
    if metadata.get("kind") != "smarter-project-watcher":
        return False
    return (
        _path_key(metadata.get("project_root", "")) == _path_key(project_root)
        and _path_key(metadata.get("watcher_script", "")) == _path_key(watcher_script)
    )


def _script_allowed_for_root(project_root: Path, watcher_script: Path) -> bool:
    owner = _script_project_root(watcher_script)
    return owner is None or _path_key(owner) == _path_key(project_root)


def _ensure_watcher(project_root: Path, watcher_script: Path, log_path: Path) -> int | None:
    claude_dir = project_root / ".claude"
    pid_path = claude_dir / "watcher.pid"
    metadata_path = _watcher_metadata_path(project_root)
    existing_pid = _read_pid(pid_path)
    metadata = _read_json(metadata_path)

    if not _script_allowed_for_root(project_root, watcher_script):
        _emit(
            "watcher 未启动：当前 hook 脚本不属于该 project_root，"
            f"watcher_script={watcher_script}"
        )
        return None

    if _pid_alive(existing_pid):
        if _watcher_is_current(project_root, watcher_script, metadata):
            return existing_pid
        if (
            metadata.get("kind") == "smarter-project-watcher"
            and _path_key(metadata.get("project_root", "")) == _path_key(project_root)
        ):
            assert existing_pid is not None
            _terminate_pid(existing_pid)
        else:
            _emit("watcher 已存在但缺少可信 ownership 元数据；本轮不接管该进程。")
            return existing_pid

    _safe_unlink(pid_path)
    _safe_unlink(metadata_path)
    return _spawn_watcher(project_root, watcher_script, log_path)


def _script_path(script_name: str) -> Path:
    app_root = plugin_root(__file__)
    preferred = script_path(app_root, script_name)
    if preferred.is_file():
        return preferred
    return preferred


def _read_health_warnings(report_path: Path) -> list[str]:
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if data.get("ok", True):
        return []
    warnings: list[str] = []
    for item in data.get("checks", []):
        if item.get("level") in ("warn", "error"):
            warnings.append(item.get("message", ""))
    return [warning for warning in warnings if warning]


def _startup_messages(project_root: Path) -> list[str]:
    messages: list[str] = []
    claude_dir = project_root / ".claude"

    focus_value = read_focus(claude_dir / "focus")
    if not focus_value:
        messages.append(msg("session.focus_empty"))
    else:
        topic_id = focus_topic_id(focus_value)
        topic_dir = find_topic_dir(project_root, topic_id)
        if topic_dir is None:
            messages.append(msg("session.focus_not_found", topic_id=topic_id))
        else:
            fm = parse_frontmatter(topic_dir / "card.md")
            messages.append(
                msg(
                    "session.focus",
                    focus_value=focus_value,
                    status=fm.get("status", "?"),
                    root=fm.get("root", "?"),
                )
            )
            last = last_scratch_header(topic_dir / "scratch.md")
            if last:
                messages.append(msg("session.recent", last=last))

    warnings = _read_health_warnings(claude_dir / "session_report.json")
    if warnings:
        messages.append(msg("session.health_warnings", warnings="; ".join(warnings[:3])))
    if not (project_root / "logs" / "stream.md").is_file():
        messages.append(msg("session.stream_missing"))
    if not (claude_dir / "dashboard.html").is_file():
        messages.append(msg("session.dashboard_missing"))
    return messages


def _spawn_watcher(project_root: Path, watcher_script: Path, log_path: Path) -> int | None:
    if not watcher_script.is_file():
        return None

    command = [sys.executable, str(watcher_script), str(project_root)]
    popen_kwargs: dict[str, object] = {
        "cwd": str(project_root),
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }

    if os.name == "nt":
        create_new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        detached_process = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        popen_kwargs["creationflags"] = create_new_process_group | detached_process
    else:
        popen_kwargs["start_new_session"] = True

    with log_path.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=log_file,
            **popen_kwargs,
        )
    return process.pid


def main() -> None:
    project_root: Path | None = None
    hook_root: Path | None = None
    agent = normalized_agent()
    try:
        setup_encoding()
        event = read_hook_event()
        roots = resolve_roots(event_cwd(event))
        hook_root = roots.hook_root
        hook_debug(
            "SessionStart",
            "start",
            hook_root=hook_root,
            details={
                "agent": agent,
                "root_kind": roots.kind,
                "event_keys": sorted(event.keys()),
            },
        )

        project_root = roots.project_root
        if project_root is None:
            # SessionStart 没有用户意图；未确认根（尤其 Home/根/浅层挂载）默认静默。
            # 只有 UserPromptSubmit 中出现建档/项目治理意图时，才输出风险边界与建档提示。
            return

        claude_dir = project_root / ".claude"
        spawned_pid = _ensure_watcher(
            project_root,
            _script_path("watcher.py"),
            claude_dir / "watcher.log",
        )
        if spawned_pid:
            metadata = _read_json(_watcher_metadata_path(project_root))
            if str(metadata.get("pid", "")) != str(spawned_pid):
                _emit(msg("session.watcher_spawned", pid=spawned_pid))

        for message in _startup_messages(project_root):
            _emit(message)
    except Exception as exc:
        hook_debug(
            "SessionStart",
            "exception",
            project_root=project_root,
            hook_root=hook_root,
            exc=exc,
        )
    finally:
        hook_debug(
            "SessionStart",
            "exit",
            project_root=project_root,
            hook_root=hook_root,
            details={"messages": len(_messages)},
        )
        write_context(agent, "SessionStart", _messages)
        sys.exit(0)


if __name__ == "__main__":
    main()
