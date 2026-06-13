"""Hermes compatibility layer for Jiacong Flow's original hook core.

This module is intentionally thin: Claude Code hook modules under app/hooks/lib
remain the source of truth. Hermes plugin code imports this adapter to translate
Hermes kwargs/tool params into that shared core, then formats Hermes return
values. Do not reimplement smarter-project governance logic here.
"""
from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

PLUGIN_DIR = Path(__file__).resolve().parent
APP_ROOT = PLUGIN_DIR.parent
HOOKS_DIR = APP_ROOT / "hooks"
SMARTER_DIR = PLUGIN_DIR / "smarter-project"

if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from lib.bridge import bridge_baseline_message, classify_route, routing_message  # type: ignore[import-not-found]  # noqa: E402
from lib.focus import focus_messages, focus_topic_id, focus_value  # type: ignore[import-not-found]  # noqa: E402
from lib.messages import msg, runtime_boundary_xml  # type: ignore[import-not-found]  # noqa: E402
from lib.roots import (  # type: ignore[import-not-found]  # noqa: E402
    RootResolution,
    known_project_roots,
    project_context_message,
    resolve_roots,
    route_target as _route_target,
    runtime_message_values,
    script_path,
    session_unmanaged_messages,
)
from lib.round_state import load_round_state, save_round_state  # type: ignore[import-not-found]  # noqa: E402
from lib.scratch import stop_obligation_messages  # type: ignore[import-not-found]  # noqa: E402
from lib.stream import stream_messages  # type: ignore[import-not-found]  # noqa: E402


def cwd_from_kwargs(kwargs: dict[str, Any] | None = None) -> str | None:
    """Extract a cwd-like value from Hermes hook kwargs if present.

    Priority:
    1. Explicit kwargs key (cwd, workdir, workspace, project_root)
    2. Environment variables (HERMES_CWD, TERMINAL_CWD)
    3. Return None (caller falls back to Path.cwd())
    """
    kwargs = kwargs or {}
    for key in ("cwd", "workdir", "workspace", "project_root"):
        value = kwargs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # Hermes WebUI/CLI 不传 cwd 参数，但设置 TERMINAL_CWD 环境变量。
    # 在 daemon/gateway 进程中 Path.cwd() 不等于用户项目目录，
    # 这里必须从环境变量获取，否则 resolve_roots 会找不到项目根。
    for env_key in ("HERMES_CWD", "TERMINAL_CWD"):
        value = os.environ.get(env_key, "").strip()
        if value:
            return value
    return None


def resolve(kwargs: dict[str, Any] | None = None, cwd: str | None = None) -> RootResolution:
    return resolve_roots(cwd or cwd_from_kwargs(kwargs))


def route_target(target: str | Path) -> Path | None:
    """Route a concrete touched path to its nearest confirmed Jiacong Flow root."""
    return _route_target(target)


def build_pre_llm_context(
    roots: RootResolution,
    user_message: str = "",
    *,
    is_first_turn: bool = False,
) -> str:
    """Build Hermes context from the original Claude hook message functions."""
    project_root = roots.project_root
    if project_root is None:
        if is_first_turn:
            return runtime_boundary_xml(
                [msg("runtime.current_time"), *session_unmanaged_messages(roots, PLUGIN_DIR)],
                lifecycle="pre_llm_call",
            )
        return runtime_boundary_xml(
            [msg("runtime.current_time"), msg("session.unmanaged.followup", **runtime_message_values())],
            lifecycle="pre_llm_call",
        )

    items: list[object] = []
    items.append(msg("runtime.current_time"))
    items.append(msg("hook.header"))
    items.append(project_context_message(roots, project_root))
    items.extend(focus_messages(project_root, SMARTER_DIR))
    items.extend(stream_messages(project_root, SMARTER_DIR))
    items.append(bridge_baseline_message())
    items.append(msg("framework.update_check"))

    route = classify_route(user_message or "")
    route_msg = routing_message(route)
    if route_msg:
        items.append(route_msg)

    current_focus = focus_value(project_root)
    if current_focus:
        save_round_state(project_root, focus_topic_id(current_focus), roots)

    if os.getenv("JIACONG_FLOW_HERMES_DEBUG_CONTEXT"):
        items.append(
            msg(
                "diagnostic.hermes_adapter",
                root_kind=roots.kind,
                selection=roots.selection or "—",
                reason=roots.reason,
            )
        )

    return runtime_boundary_xml(items, lifecycle="pre_llm_call")


def stop_messages(roots: RootResolution) -> list[str]:
    project_root = roots.project_root
    if project_root is None:
        return []
    state = load_round_state(project_root, roots)
    if not state:
        return []
    return stop_obligation_messages(project_root, state)


def known_roots(roots: RootResolution) -> list[Path]:
    if roots.project_root is None:
        return []
    return known_project_roots(roots)


def project_root_or_none(roots: RootResolution) -> Path | None:
    return roots.project_root


def watcher_status(project_root: Path) -> dict[str, Any]:
    pid_path, metadata_path = _watcher_existing_paths(project_root)
    metadata = _read_json(metadata_path)
    pid = _read_pid(pid_path)
    watcher_script = _watcher_script()
    return {
        "pid": pid,
        "alive": _pid_alive(pid),
        "current": bool(pid and _pid_alive(pid) and _watcher_is_current(project_root, watcher_script, metadata)),
        "metadata": metadata,
    }


def ensure_watcher(project_root: Path) -> dict[str, Any]:
    """Start watcher using Claude hook ownership rules where possible."""
    watcher_script = _watcher_script()
    log_path = watcher_log_path(project_root)
    if not watcher_script.is_file():
        return {"started": False, "reason": "watcher.py missing", "watcher_script": str(watcher_script)}
    if not _script_allowed_for_root(project_root, watcher_script):
        return {"started": False, "reason": "script_not_allowed_for_root", "watcher_script": str(watcher_script)}

    pid_path, metadata_path = _watcher_existing_paths(project_root)
    existing_pid = _read_pid(pid_path)
    metadata = _read_json(metadata_path)

    if _pid_alive(existing_pid):
        if _watcher_is_current(project_root, watcher_script, metadata):
            return {"started": False, "pid": existing_pid, "reason": "already_alive", "current": True}
        if metadata.get("kind") == "smarter-project-watcher" and _path_key(metadata.get("project_root", "")) == _path_key(project_root):
            assert existing_pid is not None
            _terminate_pid(existing_pid)
        else:
            return {"started": False, "pid": existing_pid, "reason": "untrusted_existing_watcher", "current": False}

    _safe_unlink(pid_path)
    _safe_unlink(metadata_path)
    pid = _spawn_watcher(project_root, watcher_script, log_path)
    return {"started": bool(pid), "pid": pid, "watcher_script": str(watcher_script)}


def stop_watcher(project_root: Path) -> dict[str, Any]:
    pid_path, metadata_path = _watcher_existing_paths(project_root)
    metadata = _read_json(metadata_path)
    pid = _read_pid(pid_path)
    if not _pid_alive(pid):
        _safe_unlink(pid_path)
        _safe_unlink(metadata_path)
        return {"stopped": False, "reason": "not_alive", "pid": pid}
    if metadata.get("kind") != "smarter-project-watcher":
        return {"stopped": False, "reason": "untrusted_metadata", "pid": pid}
    if _path_key(metadata.get("project_root", "")) != _path_key(project_root):
        return {"stopped": False, "reason": "metadata_project_root_mismatch", "pid": pid}
    script_owner = _script_project_root(Path(metadata.get("watcher_script", "")))
    if script_owner is not None and _path_key(script_owner) != _path_key(project_root):
        return {"stopped": False, "reason": "metadata_script_owner_mismatch", "pid": pid}

    assert pid is not None
    _terminate_pid(pid, force=False)
    _wait_for_pidfile_removal(pid_path, timeout_seconds=3.0)
    if pid_path.exists() and _pid_alive(pid):
        _terminate_pid(pid, force=True)
    if not _pid_alive(pid):
        _safe_unlink(pid_path)
        _safe_unlink(metadata_path)
        return {"stopped": True, "pid": pid}
    return {"stopped": False, "reason": "still_alive", "pid": pid}


def _watcher_script() -> Path:
    script_name = "watcher.py"
    candidate = PLUGIN_DIR / "smarter-project" / "scripts" / script_name
    if candidate.is_file():
        return candidate
    return script_path(APP_ROOT, script_name)


def _read_pid(pid_path: Path) -> int | None:
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except Exception:
        return None


def _pid_alive_windows(pid: int) -> bool:
    try:
        kernel32 = getattr(ctypes, "windll").kernel32
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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _script_project_root(path: Path) -> Path | None:
    try:
        script = path.resolve()
        if not script.exists():
            return None
    except Exception:
        return None
    for parent in script.parents:
        candidate = parent.parent if parent.name == "app" else parent
        if (candidate / ".jiacong" / "project.json").is_file():
            return candidate
        if (candidate / "topics").is_dir() and (candidate / ".claude").is_dir():
            return candidate
    return None


def watcher_pid_path(project_root: Path) -> Path:
    return project_root / ".jiacong" / "watcher.pid"


def watcher_log_path(project_root: Path) -> Path:
    return project_root / ".jiacong" / "watcher.log"


def _watcher_metadata_path(project_root: Path) -> Path:
    return project_root / ".jiacong" / "watcher.json"


def _watcher_existing_paths(project_root: Path) -> tuple[Path, Path]:
    current_pid = watcher_pid_path(project_root)
    current_metadata = _watcher_metadata_path(project_root)
    if current_pid.exists() or current_metadata.exists():
        return current_pid, current_metadata
    legacy_pid = project_root / ".claude" / "watcher.pid"
    legacy_metadata = project_root / ".claude" / "watcher.json"
    if legacy_pid.exists() or legacy_metadata.exists():
        return legacy_pid, legacy_metadata
    return current_pid, current_metadata


def _watcher_is_current(project_root: Path, watcher_script: Path, metadata: dict[str, Any]) -> bool:
    if metadata.get("kind") != "smarter-project-watcher":
        return False
    metadata_script = Path(str(metadata.get("watcher_script", "")))
    return (
        _path_key(metadata.get("project_root", "")) == _path_key(project_root)
        and (
            _path_key(metadata_script) == _path_key(watcher_script)
            or _path_key(metadata_script) == _path_key(watcher_script.resolve())
        )
    )


def _script_allowed_for_root(project_root: Path, watcher_script: Path) -> bool:
    owner = _script_project_root(watcher_script)
    return owner is None or _path_key(owner) == _path_key(project_root)


def _terminate_windows(pid: int) -> None:
    try:
        kernel32 = getattr(ctypes, "windll").kernel32
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


def _terminate_unix(pid: int, force: bool = False) -> None:
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except Exception:
        pass


def _terminate_pid(pid: int, force: bool = False) -> None:
    if os.name == "nt":
        _terminate_windows(pid)
    else:
        _terminate_unix(pid, force=force)


def _wait_for_pidfile_removal(pid_path: Path, timeout_seconds: float = 3.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if not pid_path.exists():
                return
        except Exception:
            return
        time.sleep(0.1)


def _watcher_python() -> str:
    hermes_venv_python = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"
    if hermes_venv_python.is_file():
        return str(hermes_venv_python)
    return sys.executable


def _spawn_watcher(project_root: Path, watcher_script: Path, log_path: Path) -> int | None:
    if not watcher_script.is_file():
        return None
    project_root.joinpath(".jiacong").mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    python_executable = _watcher_python()
    command = [python_executable, str(watcher_script), str(project_root)]
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
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            process = subprocess.Popen(command, stdout=log_file, stderr=log_file, **cast(Any, popen_kwargs))
    return process.pid
