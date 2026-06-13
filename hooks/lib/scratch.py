# -*- coding: utf-8 -*-
"""Scratch and stop-obligation checks."""

from __future__ import annotations

from pathlib import Path

from .focus import find_topic_dir, focus_topic_id, read_focus_state
from .messages import msg
from .roots import git_branch
from .stream import stream_line_count


def build_scratch_map(project_root: Path) -> dict[str, int]:
    scratch_map: dict[str, int] = {}
    try:
        for path in (project_root / "topics").iterdir():
            if not path.is_dir():
                continue
            tid = path.name.split("_", 1)[0]
            scratch = path / "scratch.md"
            if scratch.is_file():
                try:
                    scratch_map[tid] = len(scratch.read_text(encoding="utf-8").splitlines())
                except Exception:
                    pass
    except Exception:
        pass
    return scratch_map


def build_scratch_file_map(project_roots: list[Path]) -> dict[str, dict]:
    scratch_map: dict[str, dict] = {}
    for project_root in project_roots:
        branch = git_branch(project_root)
        try:
            topics_dir = project_root / "topics"
            for path in topics_dir.iterdir():
                if not path.is_dir():
                    continue
                scratch = path / "scratch.md"
                if not scratch.is_file():
                    continue
                topic_slug = path.name
                topic_id = topic_slug.split("_", 1)[0]
                try:
                    lines = len(scratch.read_text(encoding="utf-8").splitlines())
                except Exception:
                    continue
                scratch_map[str(scratch.resolve())] = {
                    "root": str(project_root.resolve()),
                    "branch": branch,
                    "topic_id": topic_id,
                    "topic_slug": topic_slug,
                    "path": str(scratch.resolve()),
                    "lines": lines,
                }
        except Exception:
            continue
    return scratch_map


def stop_obligation_messages(project_root: Path, state: dict) -> list[str]:
    messages: list[str] = []
    messages.extend(check_scratch_written(project_root, state))
    messages.extend(check_focus_changed(project_root, state))
    return messages


def check_scratch_written(project_root: Path, state: dict) -> list[str]:
    if isinstance(state.get("scratch_files"), dict):
        global_messages = check_global_scratch_written(project_root, state)
        if global_messages is not None:
            return global_messages

    saved_map: dict[str, int] = state.get("scratch_map", {})
    if not saved_map:
        return []

    focus_value = read_focus_state(project_root)
    if not focus_value:
        return []

    topic_id = focus_topic_id(focus_value)
    topic_dir = find_topic_dir(project_root, topic_id)
    if topic_dir is None:
        return []

    current_map = build_scratch_map(project_root)

    saved_lines = saved_map.get(topic_id, 0)
    current_lines = current_map.get(topic_id, 0)
    if current_lines > saved_lines:
        return []

    other_written = [
        tid
        for tid, cur in current_map.items()
        if tid != topic_id and cur > saved_map.get(tid, 0)
    ]

    scratch_path = topic_dir / "scratch.md"
    if other_written:
        return [
            msg(
                "stop.scratch_side_write_missing",
                other_written=", ".join(other_written),
                topic_id=topic_id,
                scratch_path=scratch_path,
            )
        ]
    return [msg("stop.scratch_missing", scratch_path=scratch_path)]


def check_global_scratch_written(project_root: Path, state: dict) -> list[str] | None:
    saved_files: dict[str, dict] = state.get("scratch_files", {})
    known_roots = [
        Path(root)
        for root in state.get("known_project_roots", [])
        if isinstance(root, str) and root.strip()
    ]
    if not known_roots:
        return None

    current_files = build_scratch_file_map(known_roots)
    changed_by_root: dict[str, list[dict]] = {}
    changed_by_root_topic: set[tuple[str, str]] = set()
    for path, current in current_files.items():
        saved = saved_files.get(path, {})
        if current.get("lines", 0) > saved.get("lines", 0):
            root = str(current.get("root", ""))
            topic_id = str(current.get("topic_id", ""))
            changed_by_root.setdefault(root, []).append(current)
            if root and topic_id:
                changed_by_root_topic.add((root, topic_id))

    touched_roots: set[str] = set()
    touched_topics: set[tuple[str, str]] = set()
    for record in state.get("touched_files", []):
        root = str(record.get("project_root", "")).strip()
        topic_id = str(record.get("topic_id", "")).strip()
        if not root:
            continue
        touched_roots.add(root)
        if topic_id:
            touched_topics.add((root, topic_id))

    if touched_roots:
        missing_topics = sorted(
            f"{root}#{topic_id}"
            for root, topic_id in touched_topics
            if (root, topic_id) not in changed_by_root_topic
        )
        if missing_topics:
            return [
                msg(
                    "stop.touched_topic_scratch_missing",
                    topics=", ".join(missing_topics),
                )
            ]

        roots_without_topic = touched_roots - {root for root, _topic_id in touched_topics}
        missing_roots = sorted(root for root in roots_without_topic if root not in changed_by_root)
        if missing_roots:
            return [
                msg(
                    "stop.touched_root_scratch_missing",
                    roots=", ".join(missing_roots),
                )
            ]
        return []

    if changed_by_root:
        return []

    focus_value = read_focus_state(project_root)
    if not focus_value:
        return []
    topic_id = focus_topic_id(focus_value)
    topic_dir = find_topic_dir(project_root, topic_id)
    if topic_dir is None:
        return []
    return [msg("stop.scratch_missing", scratch_path=topic_dir / "scratch.md")]


def check_focus_changed(project_root: Path, state: dict) -> list[str]:
    saved_focus = state.get("focus", "")
    current_focus = read_focus_state(project_root)

    if not saved_focus or not current_focus:
        return []
    if focus_topic_id(saved_focus) == focus_topic_id(current_focus):
        return []

    saved_stream = state.get("stream_lines", 0)
    current_stream = stream_line_count(project_root)
    if current_stream > saved_stream:
        return []

    return [
        msg(
            "stop.focus_log_missing",
            saved_focus=saved_focus,
            current_focus=current_focus,
        )
    ]
