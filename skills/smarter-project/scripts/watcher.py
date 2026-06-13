# -*- coding: utf-8 -*-
"""
watcher.py · 项目状态守护进程

监听话题、流水、焦点与角色库变更，防抖后调用 _lib.view 刷新派生视图。
进程管理（PID、信号、watchdog 事件循环）保留在此，数据构建已迁入 _lib/view.py。
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - 运行时给出明确提示
    FileSystemEvent = Any  # type: ignore

    class FileSystemEventHandler:  # type: ignore[no-redef]
        pass

    Observer = None  # type: ignore

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.view import rebuild_state  # noqa: E402


def _log(message: str) -> None:
    """守护进程统一 stderr 日志。"""
    print(f"[watcher] {message}", file=sys.stderr, flush=True)


def _path_key(path: Path | str) -> str:
    try:
        return str(Path(path).resolve()).casefold()
    except Exception:
        return str(path).casefold()


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


def default_pidfile(root: Path) -> Path:
    return root / ".jiacong" / "watcher.pid"


def _script_project_root() -> Path | None:
    script = Path(__file__).resolve()
    try:
        app_root = script.parents[3]
    except IndexError:
        return None
    candidate = app_root.parent
    if _is_confirmed_project_root(candidate):
        return candidate
    if (candidate / "topics").is_dir() and (candidate / ".claude").is_dir():
        return candidate
    return None


def _validate_script_owner(root: Path) -> None:
    owner = _script_project_root()
    if owner is not None and _path_key(owner) != _path_key(root):
        raise SystemExit(
            "[watcher] watcher.py 与 project_root 不属于同一工作树："
            f" script_root={owner} project_root={root}"
        )


def _metadata_path(pidfile: Path) -> Path:
    return pidfile.with_name("watcher.json")


def _write_metadata(root: Path, pidfile: Path, interval: float) -> None:
    script = Path(__file__).resolve()
    try:
        app_root = script.parents[3]
    except IndexError:
        app_root = script.parent
    payload = {
        "kind": "smarter-project-watcher",
        "pid": os.getpid(),
        "project_root": str(root),
        "watcher_script": str(script),
        "app_root": str(app_root),
        "pidfile": str(pidfile),
        "interval": interval,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _metadata_path(pidfile).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _cleanup_metadata(pidfile: Path) -> None:
    path = _metadata_path(pidfile)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if str(data.get("pid")) == str(os.getpid()):
        try:
            path.unlink()
        except OSError as exc:
            _log(f"删除 watcher.json 失败：{exc}")


class DebouncedRebuilder(FileSystemEventHandler):
    """watchdog 事件处理器：匹配目标路径后防抖重建。"""

    def __init__(self, root: Path, interval: float) -> None:
        super().__init__()
        self.root = root
        self.interval = interval
        self._timer: threading.Timer | None = None
        self._timer_lock = threading.Lock()
        self._rebuild_lock = threading.Lock()
        self._closed = False
        self._suppress_generated_until = 0.0

    def dispatch(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if self._closed:
            return
        changed = self._watched_event_path(event)
        if changed:
            self.schedule(changed)

    def schedule(self, reason: str) -> None:
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.interval, self._fire, args=(reason,))
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        with self._timer_lock:
            self._closed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def rebuild_now(self, reason: str) -> None:
        self._run_rebuild(reason)

    def _fire(self, reason: str) -> None:
        with self._timer_lock:
            self._timer = None
        self._run_rebuild(reason)

    def _run_rebuild(self, reason: str) -> None:
        with self._rebuild_lock:
            _log(f"rebuild trigger: {reason}")
            self._suppress_generated_until = time.monotonic() + max(self.interval * 3, 5.0)
            try:
                ok = rebuild_state(self.root)
                if ok:
                    _log("state.json updated")
            except Exception as exc:
                _log(f"rebuild failed: {exc}")
            finally:
                self._suppress_generated_until = time.monotonic() + max(self.interval * 3, 5.0)

    def _watched_event_path(self, event: FileSystemEvent) -> str | None:
        paths = [getattr(event, "src_path", "")]
        dest_path = getattr(event, "dest_path", "")
        if dest_path:
            paths.append(dest_path)
        for raw_path in paths:
            if not raw_path:
                continue
            path = Path(raw_path)
            if self._is_watched_path(path):
                return str(path)
        return None

    def _is_watched_path(self, path: Path) -> bool:
        try:
            rel = path.resolve().relative_to(self.root)
        except ValueError:
            return False

        parts = rel.parts
        if not parts:
            return False
        rel_posix = rel.as_posix()

        if parts[0] == "topics" and path.suffix.lower() == ".md":
            if rel_posix == "topics/_tree.md" and time.monotonic() < self._suppress_generated_until:
                return False
            return True
        if parts == ("logs", "stream.md"):
            return True
        if parts == (".jiacong", "focus.json"):
            return True
        if parts == (".claude", "focus"):
            return True
        if parts[0] == "base" and path.suffix.lower() == ".md":
            return True
        return False


def _pid_alive(pid: int) -> bool:
    """跨平台检测 PID 是否仍存活。"""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True

    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information,
                False,
                wintypes.DWORD(pid),
            )
            if not handle:
                return False
            exit_code = wintypes.DWORD()
            try:
                if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == 259  # STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _prepare_pidfile(pidfile: Path) -> None:
    """写入 PID 前检查已有守护进程。"""
    if pidfile.exists():
        try:
            existing = int(pidfile.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing = 0
        if existing and _pid_alive(existing):
            raise SystemExit(f"[watcher] pidfile 已存在且进程仍存活：{pidfile} (pid {existing})")
        try:
            pidfile.unlink()
        except OSError as exc:
            raise SystemExit(f"[watcher] 无法删除陈旧 pidfile：{exc}") from exc

    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()), encoding="utf-8")


def _cleanup_pidfile(pidfile: Path) -> None:
    """仅删除当前进程持有的 PID 文件。"""
    try:
        if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip() == str(os.getpid()):
            pidfile.unlink()
    except OSError as exc:
        _log(f"删除 pidfile 失败：{exc}")


def _watched_snapshot(root: Path, handler: DebouncedRebuilder) -> dict[str, int]:
    """构建被 watcher 关注文件的 mtime 快照，用于无 watchdog 时轮询。"""
    snapshot: dict[str, int] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if not handler._is_watched_path(path):
            continue
        try:
            snapshot[str(path.resolve())] = path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def _run_polling(root: Path, interval: float, handler: DebouncedRebuilder, stop_event: threading.Event) -> None:
    """无 watchdog 依赖时的标准库轮询 fallback。"""
    _log("watchdog 不可用，使用轮询模式")
    previous = _watched_snapshot(root, handler)
    while not stop_event.is_set():
        if stop_event.wait(interval):
            break
        current = _watched_snapshot(root, handler)
        if current != previous:
            previous = current
            handler.rebuild_now("polling")


def run(root: Path, interval: float, pidfile: Path) -> int:
    """启动 watcher 并保持运行；优先 watchdog，缺依赖时降级轮询。"""

    _validate_script_owner(root)
    _prepare_pidfile(pidfile)
    _write_metadata(root, pidfile, interval)
    handler = DebouncedRebuilder(root, interval)
    observer = Observer() if Observer is not None else None
    stop_event = threading.Event()

    def request_stop(signum: int, _frame: Any) -> None:
        _log(f"收到信号 {signum}，准备退出")
        stop_event.set()
        if observer is not None:
            observer.stop()

    old_handlers: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            old_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, request_stop)
        except (ValueError, OSError):
            pass

    try:
        if observer is not None:
            observer.schedule(handler, str(root), recursive=True)
            observer.start()
        _log(f"startup root={root} interval={interval}s pidfile={pidfile}")
        handler.rebuild_now("startup")

        if observer is None:
            _run_polling(root, interval, handler, stop_event)
        else:
            while not stop_event.is_set():
                time.sleep(0.5)
    finally:
        handler.cancel()
        if observer is not None and observer.is_alive():
            observer.stop()
        if observer is not None:
            observer.join(timeout=5)
        _cleanup_pidfile(pidfile)
        _cleanup_metadata(pidfile)
        for sig, old_handler in old_handlers.items():
            try:
                signal.signal(sig, old_handler)
            except (ValueError, OSError):
                pass
        _log("stopped")
    return 0


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="监听项目文件变化并刷新 .jiacong/dashboard/state.json。")
    parser.add_argument("project_root", help="项目根目录")
    parser.add_argument("--interval", type=float, default=2.0, help="防抖间隔秒数（默认 2.0）")
    parser.add_argument("--pidfile", default=None, help="PID 文件路径（默认 <project_root>/.jiacong/watcher.pid）")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.project_root))
    pidfile = Path(args.pidfile).resolve() if args.pidfile else default_pidfile(root)
    return run(root, max(0.1, args.interval), pidfile)


if __name__ == "__main__":
    sys.exit(main())
