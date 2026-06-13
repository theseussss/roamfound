# -*- coding: utf-8 -*-
"""Generate the static project dashboard."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root, now_datetime  # noqa: E402
from _lib.store import find_templates_dir  # noqa: E402

import importlib.util


_TASK_HEADING_RE = re.compile(r"^##\s+(T\d+)\s+(.+?)\s*$")
_SCRATCH_TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]\s*(.+?)\s*$")
_SCRATCH_LEGACY_RE = re.compile(r"^###\s+(S\d+)\s+·\s+\[(.+?)\]\s*(.+?)\s*$")
_MD_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_TERMINAL_PARENT_VALUES = {"", "null", "None", "none", "NULL", "—", "-"}
_STATUS_LABELS = {
    "⏳": "进行中",
    "✅": "已完成",
    "📦": "已封存",
    "⏸️": "已暂停",
    "⏸": "已暂停",
    "🔻": "已推翻",
    "🗑️": "已废弃",
    "🗑": "已废弃",
    "💭": "讨论中",
    "🌱": "待提炼",
    "⚠️": "阻塞中",
    "⚠": "阻塞中",
    "⬜": "未开始",
}


def _import_script(name: str) -> Any | None:
    path = Path(__file__).parent / f"{name}.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _status_icon(value: Any, default: str = "") -> str:
    text = _stringify(value).strip()
    if not text:
        return default
    return text.split()[0]


def _status_label(value: Any) -> str:
    icon = _status_icon(value)
    if icon in _STATUS_LABELS:
        return _STATUS_LABELS[icon]
    text = _stringify(value).strip()
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else text


def _split_slug(slug: str) -> tuple[str, str]:
    if "_" not in slug:
        return slug, slug
    return slug.split("_", 1)


def _read_text(path: Path, limit: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if limit is None else text[:limit]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _topic_dir(data: dict) -> Path:
    return Path(data["path"]).parent


def _plain_preview(text: str, limit: int = 180) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[\[([^\]|]+)\|?([^\]]*)\]\]", lambda m: m.group(2) or m.group(1), text)
    text = re.sub(r"[*_>#|=-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_stringify(item).strip() for item in value if _stringify(item).strip()]
    text = _stringify(value).strip()
    if not text or text in {"[]", "null", "None"}:
        return []
    return [line.strip("- ").strip() for line in text.splitlines() if line.strip("- ").strip()]


def _path_key(path: Path | str) -> str:
    try:
        return str(Path(path).resolve()).casefold()
    except Exception:
        return str(path).casefold()


def _normalize_topic_ref(ref: Any, slug_by_short: dict[str, str], known_slugs: set[str]) -> str:
    text = _stringify(ref).strip().strip('"').strip("'")
    if text in _TERMINAL_PARENT_VALUES:
        return ""
    text = text.replace("\\", "/").strip("/")
    text = text.split("#", 1)[0]
    if text.endswith(".md"):
        text = text[:-3]
    text = Path(text).name
    if text in known_slugs:
        return text
    if text in slug_by_short:
        return slug_by_short[text]
    if "_" in text:
        short = text.split("_", 1)[0]
        return slug_by_short.get(short, text if text in known_slugs else "")
    return ""


def _read_focus(root: Path, topics_by_slug: dict[str, dict]) -> dict:
    raw = ""
    focus_json = _read_json(root / ".jiacong" / "focus.json")
    topic_id = _stringify(focus_json.get("topic_id")).strip() if focus_json else ""
    if topic_id:
        raw = topic_id
    else:
        raw = _read_text(root / ".claude" / "focus").strip()
    short_to_slug = {slug.split("_", 1)[0]: slug for slug in topics_by_slug if "_" in slug}
    focus_main = raw.split(":", 1)[0].strip()
    slug = ""
    if focus_main in topics_by_slug:
        slug = focus_main
    elif focus_main in short_to_slug:
        slug = short_to_slug[focus_main]
    return {
        "raw": raw,
        "slug": slug,
        "task": raw.split(":", 1)[1].strip() if ":" in raw else "",
        "exists": bool(slug),
    }


def _extract_card_sections(card_path: Path, limit: int = 6) -> list[dict]:
    text = _read_text(card_path)
    if not text:
        return []
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    headings = list(_MD_HEADING_RE.finditer(text))
    sections: list[dict] = []
    for idx, match in enumerate(headings):
        title = match.group(2).strip()
        if title.startswith(("📑", "🔗", "💬", "🧾")):
            continue
        start = match.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        sections.append({
            "level": len(match.group(1)),
            "title": title,
            "preview": _plain_preview(body, 240) or "暂无正文",
        })
        if len(sections) >= limit:
            break
    return sections


def _extract_scratch_entries(topic_path: Path, limit: int = 7) -> list[dict]:
    path = topic_path / "scratch.md"
    text = _read_text(path)
    if not text:
        return []
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    entries: list[dict] = []
    current: dict | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current, buffer
        if not current:
            return
        body = "\n".join(buffer).strip()
        current.pop("_legacy", None)
        current["preview"] = _plain_preview(body, 220) or "暂无内容"
        entries.append(current)
        current = None
        buffer = []

    for line in text.splitlines():
        ts_match = _SCRATCH_TS_RE.match(line)
        legacy_match = _SCRATCH_LEGACY_RE.match(line)
        if ts_match and current and current.get("_legacy"):
            buffer.append(line)
            continue
        if ts_match or legacy_match:
            flush()
            if ts_match:
                current = {"time": ts_match.group(1), "title": ts_match.group(2).strip()}
            else:
                current = {
                    "time": legacy_match.group(2).strip(),
                    "title": f"{legacy_match.group(1)} {legacy_match.group(3).strip()}",
                    "_legacy": True,
                }
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return list(reversed(entries[-limit:]))


def _extract_tasks(topic_path: Path) -> list[dict]:
    path = topic_path / "tasks.md"
    text = _read_text(path)
    if not text:
        return []
    tasks: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current:
            current["status_icon"] = _status_icon(current.get("status"), "⬜")
            current["status_label"] = _status_label(current.get("status")) or "未标记"
            current["blocked"] = current["status_icon"] in {"⚠️", "⚠"} or "阻塞" in json.dumps(current, ensure_ascii=False)
            tasks.append(current)
        current = None

    labels = (
        ("status", "- **状态**："),
        ("dependency", "- **依赖**："),
        ("output", "- **产出路径**："),
        ("description", "- **说明**："),
    )
    for line in text.splitlines():
        heading = _TASK_HEADING_RE.match(line)
        if heading:
            flush()
            current = {
                "id": heading.group(1),
                "title": heading.group(2).strip(),
                "status": "",
                "dependency": "",
                "output": "",
                "description": "",
            }
            continue
        if current is None:
            continue
        stripped = line.strip()
        for key, label in labels:
            if stripped.startswith(label):
                current[key] = stripped[len(label):].strip()
                break
    flush()
    return tasks


def _file_meta(path: Path, root: Path, include_body: bool = False) -> dict:
    stat = path.stat()
    readable_suffixes = {".md", ".txt", ".json", ".html", ".htm", ".py", ".js", ".css", ".yaml", ".yml"}
    rel = path.relative_to(root).as_posix()
    meta = {
        "name": path.name,
        "rel": rel,
        "suffix": path.suffix.lower(),
        "size": stat.st_size,
        "updated": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "readable": path.suffix.lower() in readable_suffixes,
    }
    if include_body and meta["readable"]:
        body_limit = 36000
        body = _read_text(path, limit=body_limit)
        if stat.st_size > body_limit:
            body += f"\n\n<!-- dashboard: attachment truncated at {body_limit} chars -->"
        meta["body"] = body
    return meta


def _topic_attachments(topic_path: Path, include_body: bool = False) -> list[dict]:
    core_files = {"card.md", "scratch.md", "tasks.md"}
    attachments: list[dict] = []
    if not topic_path.exists():
        return attachments
    for path in sorted(topic_path.rglob("*")):
        if not path.is_file():
            continue
        if path.name in core_files:
            continue
        if any(part.startswith(".") for part in path.relative_to(topic_path).parts):
            continue
        try:
            attachments.append(_file_meta(path, topic_path, include_body=include_body))
        except OSError:
            continue
        if len(attachments) >= 80:
            break
    return attachments


def _topic_documents(topic_path: Path) -> dict:
    docs = {"card": topic_path / "card.md", "scratch": topic_path / "scratch.md", "tasks": topic_path / "tasks.md"}
    return {
        key: {
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
            "updated": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if path.exists() else "",
        }
        for key, path in docs.items()
    }


def _topic_docs_payload(data: dict) -> dict:
    topic_path = _topic_dir(data)
    return {
        "documents": {
            "card": _read_text(topic_path / "card.md"),
            "scratch": _read_text(topic_path / "scratch.md"),
            "tasks": _read_text(topic_path / "tasks.md") if (topic_path / "tasks.md").exists() else "",
        },
        "attachments": _topic_attachments(topic_path, include_body=True),
    }


def _collect_wiki_links(topic_path: Path, slug_by_short: dict[str, str], known_slugs: set[str]) -> list[str]:
    links: set[str] = set()
    for name in ("card.md", "scratch.md", "tasks.md"):
        text = _read_text(topic_path / name)
        for match in _WIKI_LINK_RE.finditer(text):
            ref = _normalize_topic_ref(match.group(1), slug_by_short, known_slugs)
            if ref:
                links.add(ref)
    return sorted(links, key=lambda slug: slug.split("_", 1)[0])


def _topic_route_order(stream_entries: list[dict], topics_by_slug: dict[str, dict]) -> list[str]:
    known_slugs = set(topics_by_slug)
    slug_by_short = {slug.split("_", 1)[0]: slug for slug in known_slugs if "_" in slug}
    order: list[str] = []
    seen: set[str] = set()
    topic_ref_re = re.compile(r"(\d{3}_[^\s，,。:：]+|\b\d{3}\b)")
    for entry in reversed(stream_entries):
        title = _stringify(entry.get("title"))
        for match in topic_ref_re.finditer(title):
            slug = _normalize_topic_ref(match.group(1), slug_by_short, known_slugs)
            if slug and slug not in seen:
                seen.add(slug)
                order.append(slug)

    def fallback_key(slug: str) -> tuple[str, str]:
        fm = topics_by_slug[slug].get("frontmatter", {})
        return (_stringify(fm.get("created") or fm.get("updated") or ""), slug.split("_", 1)[0])

    for slug in sorted(known_slugs - seen, key=fallback_key):
        order.append(slug)
    return order


def _build_graph(topics_by_slug: dict[str, dict], route_order: list[str] | None = None) -> dict:
    known_slugs = set(topics_by_slug)
    slug_by_short = {slug.split("_", 1)[0]: slug for slug in known_slugs if "_" in slug}
    parent_by_slug: dict[str, str] = {}
    links_by_slug: dict[str, list[str]] = {}

    for slug, data in topics_by_slug.items():
        fm = data.get("frontmatter", {})
        parent = _normalize_topic_ref(fm.get("parent"), slug_by_short, known_slugs)
        if parent and parent != slug:
            parent_by_slug[slug] = parent
        links_by_slug[slug] = [
            link for link in _collect_wiki_links(_topic_dir(data), slug_by_short, known_slugs)
            if link != slug
        ]

    edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, kind: str, label: str) -> None:
        if not source or not target or source == target:
            return
        key = (source, target, kind)
        if key in seen:
            return
        seen.add(key)
        edges.append({"source": source, "target": target, "kind": kind, "label": label})

    for child, parent in parent_by_slug.items():
        add_edge(parent, child, "parent", "parent")
    for source, links in links_by_slug.items():
        for target in links:
            add_edge(source, target, "link", "[[ref]]")

    ordered = [slug for slug in (route_order or []) if slug in known_slugs]
    if not ordered:
        ordered = sorted(known_slugs, key=lambda slug: slug.split("_", 1)[0])
    for prev, nxt in zip(ordered, ordered[1:]):
        add_edge(prev, nxt, "route", "讨论推进")

    by_root: dict[str, list[str]] = {}
    for slug, data in topics_by_slug.items():
        root = _stringify(data.get("frontmatter", {}).get("root") or "未归类")
        by_root.setdefault(root, []).append(slug)
    for slugs in by_root.values():
        slugs = sorted(slugs, key=lambda slug: slug.split("_", 1)[0])
        for prev, nxt in zip(slugs, slugs[1:]):
            add_edge(prev, nxt, "cluster", "same root")

    summary = {
        "nodes": len(known_slugs),
        "parent_edges": sum(1 for edge in edges if edge["kind"] == "parent"),
        "link_edges": sum(1 for edge in edges if edge["kind"] == "link"),
        "route_edges": sum(1 for edge in edges if edge["kind"] == "route"),
        "cluster_edges": sum(1 for edge in edges if edge["kind"] == "cluster"),
    }
    return {"edges": edges, "parents": parent_by_slug, "links": links_by_slug, "route_order": ordered, "summary": summary}


def _topic_payload(data: dict, graph: dict) -> dict:
    slug = data.get("slug", "")
    short_id, title = _split_slug(slug)
    fm = data.get("frontmatter", {})
    topic_path = _topic_dir(data)
    status = fm.get("status") or "⏳ 进行中"
    tasks = _extract_tasks(topic_path)
    sections = _extract_card_sections(topic_path / "card.md")
    preview = sections[0]["preview"] if sections else _plain_preview(_read_text(topic_path / "card.md", limit=24000), 260)
    return {
        "slug": slug,
        "short_id": short_id,
        "title": title,
        "root": fm.get("root") or "",
        "parent": graph["parents"].get(slug) or "",
        "links": graph["links"].get(slug, []),
        "children": sorted([child for child, parent in graph["parents"].items() if parent == slug], key=lambda item: item.split("_", 1)[0]),
        "status": status,
        "status_icon": _status_icon(status, "⏳"),
        "status_label": _status_label(status),
        "updated": _stringify(fm.get("updated") or fm.get("created") or ""),
        "created": _stringify(fm.get("created") or ""),
        "role": fm.get("role") or "",
        "acceptance_criteria": _normalize_list(fm.get("acceptance_criteria")),
        "toc": _normalize_list(fm.get("toc")),
        "path": str(topic_path),
        "documents": _topic_documents(topic_path),
        "attachments": _topic_attachments(topic_path, include_body=False),
        "sections": sections,
        "scratch_entries": _extract_scratch_entries(topic_path),
        "tasks": tasks,
        "blocked_tasks": [task for task in tasks if task.get("blocked")],
        "preview": preview,
    }


def _run_git_with_paths(git_dir: Path | None, work_tree: Path, args: list[str], timeout: float = 4) -> str:
    command = ["git"]
    if git_dir is not None:
        command += ["--git-dir", str(git_dir), "--work-tree", str(work_tree)]
    else:
        command += ["-C", str(work_tree)]
    command += args
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _find_workspace(root: Path) -> Path | None:
    for ancestor in (root, *root.parents):
        if (ancestor / ".repo.git").exists() and ((ancestor / "main").is_dir() or (ancestor / "worktrees").is_dir()):
            return ancestor
    return None


def _convert_gitdir_path(value: str, workspace: Path | None) -> Path:
    text = value.strip()
    match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", text)
    if match:
        drive = match.group(1).upper() + ":"
        return Path(drive + "\\" + match.group(2).replace("/", "\\"))
    path = Path(text)
    if not path.is_absolute() and workspace is not None:
        path = workspace / path
    return path


def _gitdir_for_worktree(worktree: Path, workspace: Path | None) -> Path | None:
    git_file = worktree / ".git"
    if not git_file.exists() or git_file.is_dir():
        return None
    try:
        raw = git_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if raw.startswith("gitdir:"):
        return _convert_gitdir_path(raw.split(":", 1)[1].strip(), workspace)
    return None


def _parse_worktree_list(workspace: Path, root: Path) -> list[dict]:
    output = _run_git_with_paths(workspace / ".repo.git", workspace, ["worktree", "list", "--porcelain"], timeout=6)
    if not output:
        return [{"path": str(root), "branch": _run_git_with_paths(_gitdir_for_worktree(root, workspace), root, ["branch", "--show-current"]) or root.name}]
    items: list[dict] = []
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            if current:
                items.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        items.append(current)

    parsed: list[dict] = []
    for item in items:
        wt = item.get("worktree", "")
        if not wt:
            continue
        path = Path(wt)
        if path == workspace / ".repo.git":
            continue
        branch = item.get("branch", "")
        branch = branch.replace("refs/heads/", "") if branch else "(detached)"
        parsed.append({"path": str(path), "branch": branch, "head": item.get("HEAD", "")[:12]})
    return parsed


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, wintypes.DWORD(pid))
            if not handle:
                return False
            exit_code = wintypes.DWORD()
            try:
                if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == 259
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _watcher_paths(worktree: Path) -> tuple[Path, Path]:
    current_dir = worktree / ".jiacong"
    current_pid = current_dir / "watcher.pid"
    current_metadata = current_dir / "watcher.json"
    if current_pid.exists() or current_metadata.exists():
        return current_pid, current_metadata
    legacy_dir = worktree / ".claude"
    return legacy_dir / "watcher.pid", legacy_dir / "watcher.json"


def _watcher_state(worktree: Path) -> dict:
    pidfile, metadata_path = _watcher_paths(worktree)
    metadata = _read_json(metadata_path)
    pid_text = ""
    try:
        pid_text = pidfile.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    pid = 0
    for candidate in (metadata.get("pid"), pid_text):
        try:
            pid = int(candidate)
            break
        except (TypeError, ValueError):
            continue
    alive = _pid_alive(pid)
    project_root = metadata.get("project_root") or ""
    watcher_script = metadata.get("watcher_script") or ""
    app_root = metadata.get("app_root") or ""
    owns_root = bool(metadata) and _path_key(project_root) == _path_key(worktree)
    owns_script = bool(metadata) and _path_key(watcher_script).startswith(_path_key(worktree / "app"))
    state = "missing"
    if alive and owns_root and owns_script:
        state = "live"
    elif alive and metadata:
        state = "mismatch"
    elif alive:
        state = "legacy"
    elif pid or metadata:
        state = "stale"
    return {
        "pid": pid,
        "pid_text": str(pid) if pid else pid_text,
        "alive": alive,
        "state": state,
        "metadata_exists": bool(metadata),
        "metadata_path": str(metadata_path),
        "project_root": project_root,
        "watcher_script": watcher_script,
        "app_root": app_root,
        "started_at": metadata.get("started_at", ""),
        "owns_root": owns_root,
        "owns_script": owns_script,
    }


def _workspace_status(root: Path) -> dict:
    workspace = _find_workspace(root)
    selected = _read_text(workspace / ".jiacong-workspace" / "current-worktree").strip() if workspace else ""
    worktrees = _parse_worktree_list(workspace, root) if workspace else [{"path": str(root), "branch": ""}]
    rows: list[dict] = []
    for item in worktrees:
        path = Path(item["path"])
        git_dir = _gitdir_for_worktree(path, workspace)
        status_lines = [line for line in _run_git_with_paths(git_dir, path, ["status", "--short"]).splitlines() if line.strip()]
        branch = item.get("branch") or _run_git_with_paths(git_dir, path, ["branch", "--show-current"]) or path.name
        watcher = _watcher_state(path)
        rows.append({
            "name": "main" if path.name == "main" else path.name,
            "path": str(path),
            "branch": branch,
            "head": item.get("head", ""),
            "selected": bool(selected and (selected == path.name or selected == branch or selected in str(path))),
            "current": _path_key(path) == _path_key(root),
            "dirty_count": len(status_lines),
            "dirty_preview": status_lines[:8],
            "watcher": watcher,
        })
    rows.sort(key=lambda row: (not row["current"], row["branch"]))
    return {
        "project_root": str(root),
        "workspace_root": str(workspace) if workspace else "",
        "selection": selected,
        "branch": next((row["branch"] for row in rows if row["current"]), ""),
        "dirty_count": next((row["dirty_count"] for row in rows if row["current"]), 0),
        "dirty_preview": next((row["dirty_preview"] for row in rows if row["current"]), []),
        "clean": next((row["dirty_count"] == 0 for row in rows if row["current"]), True),
        "worktrees": rows,
        "watcher_summary": {
            "total": len(rows),
            "live": sum(1 for row in rows if row["watcher"]["state"] == "live"),
            "mismatch": sum(1 for row in rows if row["watcher"]["state"] == "mismatch"),
            "stale": sum(1 for row in rows if row["watcher"]["state"] == "stale"),
            "legacy": sum(1 for row in rows if row["watcher"]["state"] == "legacy"),
            "dirty": sum(1 for row in rows if row["dirty_count"] > 0),
        },
    }


def _hook_status(root: Path) -> dict:
    files = [
        (".claude/settings.local.json", root / ".claude" / "settings.local.json"),
        (".codex/hooks.json", root / ".codex" / "hooks.json"),
        (".gemini/settings.json", root / ".gemini" / "settings.json"),
        (".jiacong/dashboard/state.json", root / ".jiacong" / "dashboard" / "state.json"),
        (".jiacong/dashboard/index.html", root / ".jiacong" / "dashboard" / "index.html"),
        (".jiacong/watcher.json", root / ".jiacong" / "watcher.json"),
        (".claude/dashboard.html", root / ".claude" / "dashboard.html"),
        (".claude/watcher.json", root / ".claude" / "watcher.json"),
    ]
    current = _watcher_state(root)
    return {
        "watcher": current,
        "watcher_pid": current["pid_text"],
        "watcher_alive": current["alive"],
        "files": [
            {
                "label": label,
                "exists": path.exists(),
                "updated": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if path.exists() else "",
            }
            for label, path in files
        ],
    }


def _health_context(root: Path, topics: dict) -> tuple[dict, list[dict]]:
    health_mod = _import_script("health_check")
    health: dict[str, Any] = {"warn_count": 0}
    warnings: list[dict] = []
    if not health_mod:
        return health, warnings
    checks = {
        "stream": lambda: health_mod._check_stream(root),
        "vision": lambda: health_mod._check_vision(root),
        "card_structure": lambda: health_mod._check_card_structure(topics),
        "links": lambda: health_mod._check_links(topics),
        "status_format": lambda: health_mod._check_status_format(topics),
        "status": lambda: health_mod._check_status_distribution(topics),
    }
    for key, fn in checks.items():
        try:
            result = fn()
        except Exception as exc:
            result = {"warn": True, "msg": str(exc)}
        health[key] = result
        if isinstance(result, dict) and result.get("warn"):
            msg = _stringify(result.get("msg") or key)
            parts = msg.split("，", 1)
            warnings.append({"level": "warn", "message": f"[{key}] {parts[0]}", "hint": parts[1] if len(parts) > 1 else ""})
    health["warn_count"] = len(warnings)
    return health, warnings


def _stream_kind(title: str) -> tuple[str, str]:
    if "签到" in title:
        return "签到", "signin"
    if "签退" in title:
        return "签退", "signout"
    if "进展" in title or "完成" in title:
        return "进展", "progress"
    if "侧写" in title:
        return "侧写", "sidewrite"
    if "审查" in title or "排查" in title or "修复" in title:
        return "处理", "progress"
    return "事件", "event"


def _read_stream_entries(root: Path) -> list[dict]:
    text = _read_text(root / "logs" / "stream.md")
    entries: list[dict] = []
    current: dict | None = None
    buffer: list[str] = []
    heading_re = re.compile(r"^###\s+\[([^\]]+)\]\s+(.+?)\s*$")
    for line in text.splitlines():
        match = heading_re.match(line)
        if match:
            if current:
                current["detail"] = _plain_preview("\n".join(buffer), 260)
                entries.append(current)
            title = match.group(2).strip()
            kind, kind_class = _stream_kind(title)
            current = {
                "time": match.group(1).strip(),
                "title": title,
                "kind": kind,
                "kind_class": kind_class,
                "detail": "",
            }
            buffer = []
        elif current:
            buffer.append(line)
    if current:
        current["detail"] = _plain_preview("\n".join(buffer), 260)
        entries.append(current)
    return list(reversed(entries[-24:]))


def _build_payload(context: dict) -> tuple[str, str]:
    first_screen = {
        "generated_at": context.get("generated_at"),
        "project_name": context.get("project_name"),
        "project_root": context.get("project_root"),
        "focus": context.get("focus_detail"),
        "topics": context.get("all_topics"),
        "graph": context.get("graph"),
        "warnings": context.get("warnings"),
        "workspace": context.get("workspace_status"),
        "hooks": context.get("hook_status"),
        "timeline": context.get("timeline"),
        "stream_preview": context.get("stream_preview"),
        "documents": context.get("global_documents_light"),
        "task_summary": context.get("task_summary"),
    }
    docs = {"topics": context.get("topic_docs"), "documents": context.get("global_documents")}
    return (
        json.dumps(first_screen, ensure_ascii=False, separators=(",", ":")),
        json.dumps(docs, ensure_ascii=False, separators=(",", ":")),
    )


def _build_context(root: Path) -> dict:
    focus_mod = _import_script("focus_breadcrumb")
    from _lib.topics_loader import load_topics

    try:
        topics: dict = load_topics(root)
    except Exception:
        topics = {}
    topics_by_slug = {data["slug"]: data for data in topics.values()}
    stream_entries = _read_stream_entries(root)
    route_order = _topic_route_order(stream_entries, topics_by_slug)
    graph = _build_graph(topics_by_slug, route_order)
    focus = _read_focus(root, topics_by_slug)
    breadcrumb = ""
    if focus_mod and hasattr(focus_mod, "compute_breadcrumb"):
        try:
            breadcrumb = focus_mod.compute_breadcrumb(root)
        except Exception:
            breadcrumb = ""

    all_topics = [_topic_payload(data, graph) for data in topics_by_slug.values()]
    all_topics.sort(key=lambda item: item["short_id"])
    focus_topic = next((item for item in all_topics if item["slug"] == focus["slug"]), None)
    all_tasks = [
        dict(task, topic_slug=topic["slug"], topic_id=topic["short_id"], topic_title=topic["title"])
        for topic in all_topics
        for task in topic["tasks"]
    ]
    blocked_tasks = [task for task in all_tasks if task.get("blocked")]
    health, warnings = _health_context(root, topics)
    stream_body = _read_text(root / "logs" / "stream.md")
    tree_body = _read_text(root / "topics" / "_tree.md")
    topic_docs = {data["slug"]: _topic_docs_payload(data) for data in topics_by_slug.values()}
    stream_preview = stream_entries[0]["detail"] if stream_entries else _plain_preview(stream_body, 260)

    context: dict = {
        "project_name": root.name,
        "project_root": str(root),
        "generated_at": now_datetime(),
        "all_topics": all_topics,
        "topic_docs": topic_docs,
        "graph": graph,
        "warnings": warnings,
        "health": health,
        "focus_detail": {**focus, "breadcrumb": breadcrumb, "topic": focus_topic},
        "task_summary": {
            "total": len(all_tasks),
            "blocked": len(blocked_tasks),
            "done": sum(1 for task in all_tasks if task.get("status_icon") == "✅"),
            "active": sum(1 for task in all_tasks if task.get("status_icon") == "⏳"),
            "todo": sum(1 for task in all_tasks if task.get("status_icon") == "⬜"),
            "blocked_items": blocked_tasks[:8],
        },
        "workspace_status": _workspace_status(root),
        "hook_status": _hook_status(root),
        "timeline": stream_entries,
        "stream_preview": stream_preview,
        "global_documents_light": {
            "tree": {"title": "话题树", "exists": bool(tree_body), "preview": _plain_preview(tree_body, 220)},
            "stream": {"title": "项目流水", "exists": bool(stream_body), "preview": _plain_preview(stream_body, 220)},
        },
        "global_documents": {
            "tree": {"title": "话题树", "kind": "markdown", "body": tree_body},
            "stream": {"title": "项目流水", "kind": "markdown", "body": stream_body},
        },
    }
    context["dashboard_payload"], context["dashboard_docs_payload"] = _build_payload(context)
    return context


def _dashboard_output_path(root: Path) -> Path:
    return root / ".jiacong" / "dashboard" / "index.html"


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="生成 .jiacong/dashboard/index.html。")
    parser.add_argument("root", help="项目根目录")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    templates_dir = find_templates_dir(__file__)
    tmpl_path = templates_dir / "project" / "dashboard.html.tmpl"
    if not tmpl_path.exists():
        print(f"[错误] 模板不存在：{tmpl_path}", file=sys.stderr)
        return 2
    try:
        from jinja2 import Template  # type: ignore
    except ImportError:
        print("[错误] dashboard.py 需要 jinja2；请 pip install jinja2", file=sys.stderr)
        return 2

    context = _build_context(root)
    html = Template(tmpl_path.read_text(encoding="utf-8"), keep_trailing_newline=True).render(**context)
    out_path = _dashboard_output_path(root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[ok] {out_path}")
    print(
        f"     话题 {len(context['all_topics'])} 个，"
        f"关系 {len(context['graph']['edges'])} 条，"
        f"健康告警 {context['health'].get('warn_count', 0)} 项"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
