# -*- coding: utf-8 -*-
"""Best-effort hook debug logging."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .roots import WORKSPACE_STATE_DIR, resolve_roots


def hook_debug(
    event: str,
    status: str,
    *,
    project_root: Path | None = None,
    hook_root: Path | None = None,
    details: dict[str, Any] | None = None,
    exc: BaseException | None = None,
) -> None:
    try:
        path = _hook_debug_path(project_root=project_root, hook_root=hook_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            "status": status,
            "cwd": str(Path.cwd()),
            "argv": sys.argv,
            "pid": os.getpid(),
        }
        if details:
            payload["details"] = details
        if exc is not None:
            payload["error"] = f"{type(exc).__name__}: {exc}"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _hook_debug_path(
    *,
    project_root: Path | None = None,
    hook_root: Path | None = None,
) -> Path:
    if project_root is not None:
        return project_root / ".claude" / "hook_debug.log"
    if hook_root is not None:
        return hook_root / WORKSPACE_STATE_DIR / "hook_debug.log"
    try:
        roots = resolve_roots()
        if roots.project_root is not None:
            return roots.project_root / ".claude" / "hook_debug.log"
        if roots.hook_root is not None:
            return roots.hook_root / WORKSPACE_STATE_DIR / "hook_debug.log"
    except Exception:
        pass
    return Path.cwd() / WORKSPACE_STATE_DIR / "hook_debug.log"
