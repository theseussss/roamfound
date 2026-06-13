# -*- coding: utf-8 -*-
"""Per-turn state persisted between UserPromptSubmit and Stop."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .focus import read_focus
from .roots import (
    RootResolution,
    git_branch,
    known_project_roots,
    state_dir,
    workspace_state_dir,
)
from .scratch import build_scratch_file_map, build_scratch_map
from .stream import stream_line_count


def save_round_state(
    project_root: Path,
    topic_id: str,
    roots: RootResolution | None = None,
) -> None:
    focus_value = read_focus(project_root / ".claude" / "focus")
    project_roots = known_project_roots(roots) if roots is not None else [project_root]
    state = {
        "version": 2,
        "focus": focus_value,
        "topic_id": topic_id,
        "active_project_root": str(project_root.resolve()),
        "active_branch": git_branch(project_root),
        "known_project_roots": [str(root.resolve()) for root in project_roots],
        "scratch_files": build_scratch_file_map(project_roots),
        "scratch_map": build_scratch_map(project_root),
        "stream_lines": stream_line_count(project_root),
        "ts": datetime.now().isoformat(),
    }
    for state_path in _round_state_paths(project_root, roots):
        try:
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def load_round_state(
    project_root: Path,
    roots: RootResolution | None = None,
) -> dict | None:
    for state_path in _round_state_paths(project_root, roots, create=False):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                state["touched_files"] = load_touched_files(state, project_root, roots)
                return state
        except Exception:
            continue
    return None


def round_touched_paths(project_root: Path, roots: RootResolution | None = None) -> list[Path]:
    paths: list[Path] = []
    if roots is not None and roots.workspace_root is not None:
        paths.append(workspace_state_dir(roots.workspace_root) / "round_touched.jsonl")
    paths.append(state_dir(project_root) / "round_touched.jsonl")
    paths.append(project_root / ".claude" / ".round_touched.jsonl")
    return paths


def load_touched_files(
    state: dict,
    project_root: Path,
    roots: RootResolution | None = None,
) -> list[dict]:
    records: list[dict] = []
    since = str(state.get("ts", ""))
    for path in round_touched_paths(project_root, roots):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if since and str(record.get("ts", "")) <= since:
                    continue
                records.append(record)
        except Exception:
            continue
    return records


def _round_state_paths(
    project_root: Path,
    roots: RootResolution | None = None,
    *,
    create: bool = True,
) -> list[Path]:
    paths: list[Path] = []
    if roots is not None and roots.workspace_root is not None:
        base = workspace_state_dir(roots.workspace_root) if create else roots.workspace_root / ".jiacong-workspace"
        paths.append(base / "round_state.json")
    if create:
        paths.append(state_dir(project_root) / "round_state.json")
    else:
        paths.append(project_root / ".jiacong" / "round_state.json")
        paths.append(project_root / ".claude" / ".round_state.json")
    return paths
