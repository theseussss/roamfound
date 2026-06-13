# -*- coding: utf-8 -*-
"""Focus/topic helpers for UserPromptSubmit and SessionStart hooks.

权威源优先级：
1. <project>/.jiacong/focus.json —— Jiacong Flow 自身状态源。
2. <project>/.claude/focus —— 旧项目兼容入口。

focus 只锚定话题。任务属于 topics/<NNN>/tasks.md，不进入全局 focus。
展示用 breadcrumb 不能作为写入落点的权威源。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .messages import msg

FOCUS_JSON = Path(".jiacong") / "focus.json"
LEGACY_FOCUS = Path(".claude") / "focus"


def focus_json_path(project_root: Path) -> Path:
    return project_root / FOCUS_JSON


def legacy_focus_path(project_root: Path) -> Path:
    return project_root / LEGACY_FOCUS


def read_focus(focus_path: Path) -> str:
    """兼容旧调用：传入 .claude/focus 时，优先改读同项目 .jiacong/focus.json。"""
    project_root = _project_root_from_focus_path(focus_path)
    if project_root is not None:
        state = read_focus_state(project_root)
        if state.get("topic_id"):
            return str(state["topic_id"])
    return _read_legacy_focus_file(focus_path)


def read_focus_state(project_root: Path) -> dict[str, Any]:
    """读取 focus 状态对象；JSON 优先，旧文本 fallback。"""
    state = _read_focus_json(focus_json_path(project_root))
    if state.get("topic_id"):
        return state
    legacy = _read_legacy_focus_file(legacy_focus_path(project_root))
    if not legacy:
        return {}
    topic_id = _topic_id_from_focus_value(legacy)
    if not topic_id:
        return {}
    return {
        "schema_version": 1,
        "topic_id": topic_id,
        "source": "legacy_fallback",
    }


def write_focus_state(
    project_root: Path,
    topic_id: str,
    *,
    source: str = "manual",
    mirror_legacy: bool = False,
) -> dict[str, Any]:
    """写入 .jiacong/focus.json；旧 .claude/focus 只在显式要求时镜像。"""
    topic_id = str(topic_id).strip()
    if not topic_id:
        raise ValueError("topic_id is required")
    state = {
        "schema_version": 1,
        "topic_id": topic_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
    }
    path = focus_json_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mirror_legacy:
        legacy_path = legacy_focus_path(project_root)
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(topic_id + "\n", encoding="utf-8")
    return state


def focus_value(project_root: Path) -> str:
    return str(read_focus_state(project_root).get("topic_id") or "")


def focus_topic_id(focus_value_or_state: str | dict[str, Any]) -> str:
    if isinstance(focus_value_or_state, dict):
        return str(focus_value_or_state.get("topic_id") or "").strip()
    return _topic_id_from_focus_value(str(focus_value_or_state or ""))


def _read_focus_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    topic_id = str(data.get("topic_id") or "").strip()
    if not topic_id:
        return {}
    return {**data, "topic_id": topic_id}


def _read_legacy_focus_file(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    for line in raw.splitlines():
        value = line.strip()
        if value:
            return value
    return ""


def _project_root_from_focus_path(focus_path: Path) -> Path | None:
    parts = focus_path.parts
    if len(parts) >= 2 and parts[-2:] == (".claude", "focus"):
        return focus_path.parent.parent
    if len(parts) >= 2 and parts[-2:] == (".jiacong", "focus.json"):
        return focus_path.parent.parent
    return None


def _topic_id_from_focus_value(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    topic_part = raw.split(":", 1)[0].strip()
    if "_" in topic_part:
        return topic_part.split("_", 1)[0].strip()
    return topic_part[:3].strip()


def topic_exists(project_root: Path, topic_id: str) -> bool:
    if not topic_id:
        return False
    try:
        return any(path.is_dir() for path in (project_root / "topics").glob(f"{topic_id}_*"))
    except Exception:
        return False


def find_topic_dir(project_root: Path, topic_id: str) -> Path | None:
    try:
        for path in (project_root / "topics").glob(f"{topic_id}_*"):
            if path.is_dir():
                return path
    except Exception:
        pass
    return None


def parse_frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key in ("topic_id", "status", "root", "parent", "role"):
                result[key] = value
    return result


def last_scratch_header(scratch_path: Path) -> str:
    try:
        text = scratch_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    last = ""
    for line in text.splitlines():
        if line.startswith("### S"):
            last = line
    return last.lstrip("#").strip()


def focus_messages(project_root: Path, skill_dir: Path) -> list[str]:
    focus_state = read_focus_state(project_root)
    focus_value = str(focus_state.get("topic_id") or "")
    if not focus_value:
        return [
            msg("focus.missing.header"),
            msg("focus.missing.tree", tree_script=skill_dir / "scripts" / "tree_gen.py", project_root=project_root),
            msg(
                "focus.missing.new",
                topic_new_script=skill_dir / "scripts" / "topic_new.py",
                project_root=project_root,
            ),
            msg("focus.missing.set", focus_path=focus_json_path(project_root)),
        ]

    topic_id = focus_topic_id(focus_state)
    if not topic_exists(project_root, topic_id):
        return [msg("focus.not_found", topic_id=topic_id)]

    messages = topic_context_messages(project_root, topic_id, focus_value)
    messages.append(msg("focus.classify_required", focus_value=focus_value))
    messages.append(msg("focus.classify_options"))
    return messages


def topic_context_messages(project_root: Path, topic_id: str, focus_value: str) -> list[str]:
    topic_dir = find_topic_dir(project_root, topic_id)
    if topic_dir is None:
        return []

    fm = parse_frontmatter(topic_dir / "card.md")
    status = fm.get("status", "?")
    root = fm.get("root", "?")
    parent = fm.get("parent", "—")
    focus_display = topic_dir.name

    if parent and parent not in ("—", "null", "None", ""):
        breadcrumb = msg(
            "focus.breadcrumb.parent",
            root=root,
            parent=parent,
            focus_value=focus_display,
            status=status,
        )
    else:
        breadcrumb = msg(
            "focus.breadcrumb",
            root=root,
            focus_value=focus_display,
            status=status,
        )
    return [breadcrumb]
