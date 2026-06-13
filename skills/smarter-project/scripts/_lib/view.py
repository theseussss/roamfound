# -*- coding: utf-8 -*-
"""
view · 派生视图生成

从 canonical state（topics/、logs/、base/perspectives/、.jiacong/focus.json）单向生成
派生产物（_tree.md、dashboard/index.html、dashboard/state.json），不反向修改 canonical。

函数返回数据，不向 stderr 输出——日志由调用者（watcher/脚本壳）负责。
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

try:
    from .data import load_topics, now_datetime
except ImportError:
    from data import load_topics, now_datetime  # type: ignore

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_TERMINAL_PARENT_VALUES = {"", "null", "None", "none", "NULL", "—", "-"}
_SCRATCH_BASELINE = {"💭": 0, "🌱": 0, "📦": 0}


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #

def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _status_icon(status: Any, default: str = "⏳") -> str:
    text = _stringify(status).strip()
    if not text:
        return default
    parts = text.split()
    return parts[0] if parts else default


def _split_slug(slug: str) -> tuple[str, str]:
    if "_" not in slug:
        return slug, slug
    short_id, title = slug.split("_", 1)
    return short_id, title


def _normalize_parent(
    parent: Any,
    short_to_slug: dict[str, str],
    by_slug: dict[str, dict],
) -> str | None:
    text = _stringify(parent).strip()
    if text in _TERMINAL_PARENT_VALUES:
        return None
    if text in by_slug:
        return text
    return short_to_slug.get(text, text)


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_stringify(item) for item in value if _stringify(item).strip()]
    text = _stringify(value).strip()
    if not text or text in {"[]", "null", "None"}:
        return []
    return [
        line.strip("- ").strip()
        for line in text.splitlines()
        if line.strip("- ").strip()
    ]


# --------------------------------------------------------------------------- #
# 读取函数
# --------------------------------------------------------------------------- #

def _read_frontmatter_status(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not text.startswith("---"):
        return ""
    for line in text.splitlines()[1:]:
        stripped = line.rstrip()
        if stripped == "---":
            break
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        if key.strip() == "status":
            return _status_icon(value.strip().strip('"').strip("'"), default="")
    return ""


def _extract_mermaid(root: Path) -> str | None:
    tree_path = root / "topics" / "_tree.md"
    if not tree_path.exists():
        return None
    try:
        text = tree_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"```mermaid\s*\n(.*?)\n```", text, re.DOTALL)
    return match.group(1).strip() if match else ""


# --------------------------------------------------------------------------- #
# 脚本集成（临时层，Step 5 后由直接 _lib 调用替代）
# --------------------------------------------------------------------------- #

def _import_script(name: str) -> Any | None:
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        if name in sys.modules:
            return importlib.reload(sys.modules[name])
        return importlib.import_module(name)
    except Exception:
        return None


def _run_script_main(name: str, root: Path) -> bool:
    module = _import_script(name)
    if module is None:
        return False
    main_fn = getattr(module, "main", None)
    if not callable(main_fn):
        return False

    old_argv = sys.argv[:]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        sys.argv = [str(_SCRIPTS_DIR / f"{name}.py"), str(root)]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main_fn()
    except SystemExit as exc:
        result = exc.code
    except Exception:
        return False
    finally:
        sys.argv = old_argv

    return result in (0, None)


# --------------------------------------------------------------------------- #
# 复合构建器
# --------------------------------------------------------------------------- #

def _load_topics_state(
    root: Path,
) -> tuple[list[dict] | None, dict[str, int] | None, dict | None]:
    try:
        topics = load_topics(root)
    except Exception:
        return None, None, None

    by_slug = {data["slug"]: data for data in topics.values()}
    short_to_slug = {
        data["slug"].split("_", 1)[0]: data["slug"]
        for data in topics.values()
        if "_" in data["slug"]
    }

    children: dict[str, list[str]] = {slug: [] for slug in by_slug}
    normalized_parent: dict[str, str | None] = {}
    for slug, data in by_slug.items():
        parent = _normalize_parent(
            data.get("frontmatter", {}).get("parent"),
            short_to_slug,
            by_slug,
        )
        normalized_parent[slug] = parent
        if parent in children:
            children[parent].append(slug)

    items: list[dict] = []
    scratch_distribution = dict(_SCRATCH_BASELINE)
    for slug, data in sorted(
        by_slug.items(), key=lambda item: _split_slug(item[0])[0]
    ):
        fm = data.get("frontmatter", {})
        short_id, title = _split_slug(slug)
        status = _stringify(fm.get("status") or "⏳ 进行中")
        scratch_status = _read_frontmatter_status(
            Path(data["path"]).parent / "scratch.md"
        )
        if scratch_status:
            scratch_distribution[scratch_status] = (
                scratch_distribution.get(scratch_status, 0) + 1
            )

        child_slugs = sorted(
            children.get(slug, []),
            key=lambda child: _split_slug(child)[0],
        )
        items.append({
            "slug": slug,
            "short_id": short_id,
            "title": title,
            "status": status,
            "status_icon": _status_icon(status),
            "root": _stringify(fm.get("root")),
            "parent": normalized_parent.get(slug),
            "updated": _stringify(fm.get("updated") or fm.get("created")),
            "scratch_status": scratch_status,
            "has_tasks": (Path(data["path"]).parent / "tasks.md").exists(),
            "acceptance_criteria": _normalize_list(fm.get("acceptance_criteria")),
            "children": child_slugs,
        })

    return items, scratch_distribution, topics


def _build_focus(root: Path) -> dict:
    raw = ""
    focus_json = root / ".jiacong" / "focus.json"
    try:
        data = json.loads(focus_json.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            raw = _stringify(data.get("topic_id")).strip()
    except Exception:
        pass
    if not raw:
        focus_path = root / ".claude" / "focus"
        try:
            if focus_path.exists():
                raw = focus_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            pass

    breadcrumb = None
    module = _import_script("focus_breadcrumb")
    compute = getattr(module, "compute_breadcrumb", None) if module else None
    if callable(compute):
        try:
            breadcrumb = compute(root)
        except Exception:
            pass
    return {"raw": raw, "breadcrumb": breadcrumb}


def _build_active_topics(root: Path) -> list[dict] | None:
    module = _import_script("active_topics")
    compute = getattr(module, "compute_active", None) if module else None
    if not callable(compute):
        return None
    try:
        active = compute(root, days=0, limit=0)
    except Exception:
        return None

    items: list[dict] = []
    for item in active:
        slug = _stringify(item.get("slug"))
        _, title = _split_slug(slug)
        items.append({
            "slug": slug,
            "status_icon": _stringify(
                item.get("status") or item.get("status_icon") or "⏳"
            ),
            "title": title,
            "root": _stringify(item.get("root")),
            "updated": _stringify(item.get("updated")),
        })
    return items


def _build_health(root: Path, topics: dict | None) -> dict | None:
    module = _import_script("health_check")
    if module is None:
        return None

    health: dict[str, Any] = {
        "stream_lines": 0,
        "stream_size_kb": 0,
        "stream_warning": False,
        "vision_days_since_update": None,
        "vision_warning": False,
        "broken_links": 0,
        "status_issues": 0,
        "warnings": [],
    }

    def add_warning(key: str, result: dict | None) -> None:
        if result and result.get("warn"):
            message = result.get("msg") or key
            health["warnings"].append(f"[{key}] {message}")

    try:
        stream = module._check_stream(root)
        health["stream_lines"] = int(stream.get("lines", 0))
        health["stream_size_kb"] = round(float(stream.get("size", 0)) / 1024, 1)
        health["stream_warning"] = bool(stream.get("warn"))
        add_warning("stream", stream)
    except Exception as exc:
        health["warnings"].append(f"[stream] {exc}")

    try:
        vision = module._check_vision(root)
        health["vision_days_since_update"] = vision.get("days_since_update")
        health["vision_warning"] = bool(vision.get("warn"))
        add_warning("vision", vision)
    except Exception as exc:
        health["warnings"].append(f"[vision] {exc}")

    if topics is None:
        return health

    try:
        card_structure = module._check_card_structure(topics)
        add_warning("card_structure", card_structure)
    except Exception as exc:
        health["warnings"].append(f"[card_structure] {exc}")

    try:
        links = module._check_links(topics)
        health["broken_links"] = int(links.get("total", 0))
        add_warning("links", links)
    except Exception as exc:
        health["warnings"].append(f"[links] {exc}")

    try:
        status_format = module._check_status_format(topics)
        health["status_issues"] = len(status_format.get("bad", []))
        add_warning("status_format", status_format)
    except Exception as exc:
        health["warnings"].append(f"[status_format] {exc}")

    return health


def _parse_role_cell(cell: str) -> tuple[str, str]:
    wiki = re.search(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", cell)
    if wiki:
        role_id = Path(wiki.group(1)).stem
        name = wiki.group(2) or role_id
        return role_id, name

    md_link = re.search(r"\[([^\]]+)\]\(([^)]+)\)", cell)
    if md_link:
        name = md_link.group(1).strip()
        role_id = Path(md_link.group(2)).stem or name
        return role_id, name

    text = re.sub(r"`([^`]+)`", r"\1", cell).strip()
    return text, text


def _parse_roles(root: Path) -> list[dict]:
    index_path = root / "base" / "perspectives" / "_index.md"
    if not index_path.exists():
        return []
    try:
        lines = index_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    roles: list[dict] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or "|" not in stripped[1:]:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        compact = "".join(cells)
        if cells[0] == "角色" or compact and set(compact) <= {":", "-"}:
            continue
        role_id, name = _parse_role_cell(cells[0])
        if not role_id and not name:
            continue
        roles.append({
            "role_id": role_id,
            "name": name,
            "scene": cells[1],
            "created": cells[2],
        })
    return roles


def _read_flow_events(root: Path) -> list[dict]:
    log_path = root / ".claude" / "flow-log.jsonl"
    if not log_path.exists():
        return []
    events: deque[dict] = deque(maxlen=20)
    try:
        with open(log_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    events.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return list(events)


# --------------------------------------------------------------------------- #
# 状态写入
# --------------------------------------------------------------------------- #

def write_state(root: Path, state: dict) -> None:
    state_dir = root / ".jiacong" / "dashboard"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "state.json"
    temp_path = state_dir / "state.json.tmp"
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    temp_path.write_text(payload + "\n", encoding="utf-8")
    temp_path.replace(state_path)


# --------------------------------------------------------------------------- #
# 公开接口
# --------------------------------------------------------------------------- #

def build_state(root: Path) -> dict:
    """汇总全部派生数据为 state.json 结构，不写文件。"""
    topics, scratch_distribution, raw_topics = _load_topics_state(root)
    return {
        "generated_at": now_datetime(),
        "focus": _build_focus(root),
        "topics": topics,
        "tree_mermaid": _extract_mermaid(root),
        "active_topics": _build_active_topics(root),
        "health": _build_health(root, raw_topics),
        "roles": _parse_roles(root),
        "scratch_distribution": scratch_distribution,
        "flow_events": _read_flow_events(root),
    }


def rebuild_state(root: Path) -> bool:
    """刷新派生脚本（tree_gen, dashboard）并写入 state.json。"""
    _run_script_main("tree_gen", root)
    _run_script_main("dashboard", root)
    state = build_state(root)
    try:
        write_state(root, state)
    except OSError:
        return False
    return True
