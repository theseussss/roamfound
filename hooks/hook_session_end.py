# -*- coding: utf-8 -*-
"""
SessionEnd 钩子。

在 Claude Code 会话结束时停止 watcher.py 守护进程，并保存健康检查报告。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.agents import normalized_agent
from lib.events import event_cwd, read_hook_event, setup_encoding
from lib.messages import msg
from lib.output import write_context
from lib.roots import plugin_root, resolve_roots, script_path


def _setup_encoding() -> None:
    setup_encoding()


_messages: list[str] = []


def _emit(msg: str) -> None:
    """收集消息，最后统一以 JSON 协议输出。"""
    _messages.append(msg)


def _flush_output(event_name: str = "SessionEnd") -> None:
    """将收集的消息以 hookSpecificOutput JSON 协议写入 stdout。"""
    write_context(normalized_agent(), event_name, _messages)


def _read_hook_event() -> dict:
    return read_hook_event()


def _find_project_root(cwd: str | Path | None = None) -> Path | None:
    return resolve_roots(cwd).project_root


def _read_pid(pid_path: Path) -> int | None:
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return int(raw)
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


def _hook_allowed_for_root(project_root: Path) -> bool:
    owner = _script_project_root(Path(__file__))
    return owner is None or _path_key(owner) == _path_key(project_root)


def _watcher_metadata_path(pid_path: Path) -> Path:
    return pid_path.with_name("watcher.json")


def _terminate_windows(pid: int) -> None:
    try:
        kernel32 = ctypes.windll.kernel32
        process_terminate = 0x0001

        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

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


def _script_path(script_name: str) -> Path:
    return script_path(plugin_root(__file__), script_name)


def _stop_watcher(pid_path: Path, project_root: Path) -> None:
    pid = _read_pid(pid_path)
    metadata = _read_json(_watcher_metadata_path(pid_path))
    if not _pid_alive(pid):
        try:
            if pid_path.exists():
                pid_path.unlink()
            if _watcher_metadata_path(pid_path).exists():
                _watcher_metadata_path(pid_path).unlink()
        except Exception:
            pass
        return

    if metadata.get("kind") != "smarter-project-watcher":
        return
    if _path_key(metadata.get("project_root", "")) != _path_key(project_root):
        return
    script_owner = _script_project_root(Path(metadata.get("watcher_script", "")))
    if script_owner is not None and _path_key(script_owner) != _path_key(project_root):
        return

    assert pid is not None
    _terminate_pid(pid, force=False)
    _wait_for_pidfile_removal(pid_path, timeout_seconds=3.0)

    try:
        pidfile_still_exists = pid_path.exists()
    except Exception:
        pidfile_still_exists = False

    if pidfile_still_exists and _pid_alive(pid):
        _terminate_pid(pid, force=True)

    try:
        if not _pid_alive(pid) and pid_path.exists():
            pid_path.unlink()
        if not _pid_alive(pid) and _watcher_metadata_path(pid_path).exists():
            _watcher_metadata_path(pid_path).unlink()
    except Exception:
        pass


def _run_health_check(project_root: Path, report_path: Path, health_check_path: Path) -> None:
    try:
        if not health_check_path.is_file():
            payload = {
                "ok": False,
                "error": f"health_check.py not found: {health_check_path}",
            }
            report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return

        result = subprocess.run(
            [sys.executable, str(health_check_path), str(project_root), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout.strip()
        if not output:
            payload = {
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
            }
            output = json.dumps(payload, ensure_ascii=False, indent=2)
        report_path.write_text(output, encoding="utf-8")
    except Exception as exc:
        try:
            payload = {"ok": False, "error": str(exc)}
            report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    try:
        _setup_encoding()
        event = _read_hook_event()

        project_root = _find_project_root(event_cwd(event))
        if project_root is None:
            return
        if not _hook_allowed_for_root(project_root):
            _emit("SessionEnd 跳过 watcher 停止：当前 hook 不属于该 project_root。")
            return

        claude_dir = project_root / ".claude"
        _stop_watcher(claude_dir / "watcher.pid", project_root)

        health_check_path = _script_path("health_check.py")
        _run_health_check(project_root, claude_dir / "session_report.json", health_check_path)
        _emit(msg("session.end"))
    except Exception:
        pass
    finally:
        _flush_output()
        sys.exit(0)


if __name__ == "__main__":
    main()
