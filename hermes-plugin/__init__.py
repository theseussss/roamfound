"""Hermes adapter for Jiacong Flow / smarter-project.

Self-contained plugin: all paths resolve relative to this directory.
No hard-coded absolute paths, no external source-tree references.

Install: symlink or copy this entire directory to ~/.hermes/plugins/jiacong-flow/
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from . import compat

# ── Self-contained paths ──────────────────────────────────────────────
PLUGIN_DIR = Path(__file__).resolve().parent
SMARTER = PLUGIN_DIR / "smarter-project"
ONE_TURN = PLUGIN_DIR / "one-turn-proposal"
SCRIPTS = SMARTER / "scripts"

STATE_DIR = Path.home() / ".hermes" / "jiacong-flow"
LOG_PATH = STATE_DIR / "flow-log.jsonl"
_TOPIC_RE = re.compile(r"topics[/\\](\d{3}_[^/\\]+)[/\\]")
_FILE_TOOLS = {"write_file", "patch"}


def _safe_write_jsonl(path: Path, obj: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    except Exception:
        pass
    return rows


def _run_script(script: str, project_root: str | None = None, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPTS / script)]
    if project_root:
        cmd.append(project_root)
    cmd.extend(args)
    env = os.environ.copy()
    env.setdefault("JIACONG_FLOW_PLUGIN_ROOT", str(PLUGIN_DIR))
    env.setdefault("PYTHONPATH", str(SCRIPTS))
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)


def _script_path(name: str) -> Path:
    return SCRIPTS / name


def _read_text(path: Path, limit: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[:limit]


def _focus_state(project_root: Path) -> dict[str, Any]:
    """读取 focus 权威状态；.jiacong/focus.json 优先，.claude/focus 兼容。"""
    json_path = project_root / ".jiacong" / "focus.json"
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            topic_id = str(data.get("topic_id") or "").strip()
            if topic_id:
                return {**data, "topic_id": topic_id}
    except Exception:
        pass

    for p in [project_root / ".claude" / "focus", project_root / ".jiacong-workspace" / "focus"]:
        if p.exists():
            value = _read_text(p, 300).strip()
            if value:
                topic_id = _topic_id_from_focus_value(value)
                if topic_id:
                    return {
                        "schema_version": 1,
                        "topic_id": topic_id,
                        "source": "legacy_fallback",
                    }
    return {}


def _write_focus_state(project_root: Path, topic_id: str, source: str = "migration") -> dict[str, Any]:
    topic_id = str(topic_id).strip()
    if not topic_id:
        raise ValueError("topic_id is required")
    state = {
        "schema_version": 1,
        "topic_id": topic_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
    }
    path = project_root / ".jiacong" / "focus.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def _focus(project_root: Path) -> str:
    """返回写入/路由用的权威话题 id，不返回 breadcrumb。"""
    return str(_focus_state(project_root).get("topic_id") or "")


def _focus_breadcrumb(project_root: Path) -> str:
    """返回展示用 breadcrumb；失败时回退权威 focus 值。"""
    try:
        cp = _run_script("focus_breadcrumb.py", str(project_root), timeout=10)
        if cp.returncode == 0 and cp.stdout.strip():
            return cp.stdout.strip()
    except Exception:
        pass
    return _focus(project_root)


def _topic_id_from_focus_value(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    topic_part = raw.split(":", 1)[0].strip()
    if "_" in topic_part:
        return topic_part.split("_", 1)[0].strip()
    return topic_part[:3].strip()


def _focus_topic_id(focus: str | dict[str, Any]) -> str:
    if isinstance(focus, dict):
        return str(focus.get("topic_id") or "").strip()
    return _topic_id_from_focus_value(str(focus or ""))


def _topic_dir_from_focus(project_root: Path, focus: str) -> Path | None:
    topic_id = _focus_topic_id(focus)
    if not topic_id:
        return None
    topics = project_root / "topics"
    if not topics.is_dir():
        return None
    for child in topics.iterdir():
        if child.is_dir() and (child.name == topic_id or child.name.startswith(topic_id + "_")):
            return child
    return None


def _topic_id_from_path(path: Path) -> str:
    m = _TOPIC_RE.search(str(path))
    if not m:
        return ""
    return m.group(1).split("_", 1)[0]


def _health_json(project_root: Path) -> dict[str, Any]:
    cp = _run_script("health_check.py", str(project_root), "--json", timeout=60)
    if cp.returncode != 0:
        return {"ok": False, "error": cp.stderr.strip(), "returncode": cp.returncode}
    try:
        data = json.loads(cp.stdout or "{}")
        return data if isinstance(data, dict) else {"ok": False, "error": "invalid json"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stdout": cp.stdout[:1000]}


def _health_summary(project_root: Path) -> str:
    try:
        data = _health_json(project_root)
        if data.get("error"):
            return f"health_check failed: {data.get('error')}"
        return "warn_count={}; topics={}; links_total={}".format(
            data.get("warn_count"),
            (data.get("card_structure") or {}).get("total"),
            (data.get("links") or {}).get("total"),
        )
    except Exception as exc:
        return f"health_check unavailable: {exc}"


def _scratch_line_map(project_root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    topics = project_root / "topics"
    if not topics.is_dir():
        return out
    for d in topics.iterdir():
        if not d.is_dir():
            continue
        tid = d.name.split("_", 1)[0]
        p = d / "scratch.md"
        if p.is_file():
            try:
                out[tid] = len(p.read_text(encoding="utf-8").splitlines())
            except Exception:
                pass
    return out


def _stream_line_count(project_root: Path) -> int:
    p = project_root / "logs" / "stream.md"
    try:
        return len(p.read_text(encoding="utf-8").splitlines())
    except Exception:
        return 0


def _round_state_path(project_root: Path) -> Path:
    return project_root / ".jiacong" / "round_state.hermes.json"


def _save_round_state(project_root: Path, session_id: str = "", user_message: str = "") -> None:
    state = {
        "version": 1,
        "session_id": session_id,
        "focus": _focus(project_root),
        "topic_id": _focus_topic_id(_focus(project_root)),
        "scratch_map": _scratch_line_map(project_root),
        "stream_lines": _stream_line_count(project_root),
        "ts": datetime.now().isoformat(timespec="microseconds"),
        "user_message_preview": user_message[:300],
    }
    try:
        p = _round_state_path(project_root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_round_state(project_root: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(_round_state_path(project_root).read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _append_scratch(project_root: Path, text: str, heading: str = "Hermes update") -> str:
    focus = _focus(project_root)
    topic_dir = _topic_dir_from_focus(project_root, focus)
    if not topic_dir:
        raise RuntimeError("Cannot resolve active topic from focus")
    scratch = topic_dir / "scratch.md"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_text(scratch, 2_000_000)
    nums = [int(m.group(1)) for m in re.finditer(r"^###\s+S(\d+)\b", existing, flags=re.M)]
    sid = max(nums, default=0) + 1
    stamp = datetime.now().strftime("%m-%d %H:%M")
    block = f"\n\n### S{sid:03d} · [{stamp}] {heading}\n\n{text.strip()}\n"
    with scratch.open("a", encoding="utf-8") as f:
        f.write(block)
    _safe_write_jsonl(LOG_PATH, {"ts": datetime.now().isoformat(), "event": "scratch_append", "project_root": str(project_root), "scratch": str(scratch), "sid": sid})
    return str(scratch)


def _extract_paths_from_tool(tool_name: str, args: Any, result: Any = None, base_cwd: str | Path | None = None) -> list[Path]:
    paths: list[str] = []
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {"raw": args}
    if not isinstance(args, dict):
        args = {}
    for key in ("path", "file_path", "absolute_path"):
        v = args.get(key)
        if isinstance(v, str) and v.strip():
            paths.append(v.strip())
    # patch(mode='patch') can touch multiple files; parse patch headers.
    patch_text = args.get("patch")
    if isinstance(patch_text, str):
        for m in re.finditer(r"^\*\*\*\s+(?:Update|Add|Delete) File:\s+(.+)$", patch_text, flags=re.M):
            paths.append(m.group(1).strip())
    out: list[Path] = []
    base = Path(base_cwd).expanduser() if base_cwd else Path.cwd()
    for s in paths:
        p = Path(s).expanduser()
        if not p.is_absolute():
            p = base / p
        out.append(p)
    return out


def _record_touched_file(project_root: Path, path: Path, tool_name: str) -> None:
    try:
        rp = path.resolve()
    except Exception:
        rp = path
    topic_id = _topic_id_from_path(rp)
    topic_slug = ""
    m = _TOPIC_RE.search(str(rp))
    if m:
        topic_slug = m.group(1)
    record = {
        "ts": datetime.now().isoformat(timespec="microseconds"),
        "tool_name": tool_name,
        "file_path": str(rp),
        "project_root": str(project_root.resolve()),
        "topic_slug": topic_slug,
        "topic_id": topic_id,
        "kind": rp.name,
    }
    for target in [project_root / ".jiacong" / "round_touched.jsonl", STATE_DIR / "round_touched.jsonl"]:
        _safe_write_jsonl(target, record)


def _run_flow_hook_for_path(path: Path) -> str:
    flow_hook = _script_path("flow_hook.py")
    if not flow_hook.is_file():
        return ""
    try:
        cp = subprocess.run([sys.executable, str(flow_hook), "--file", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return "\n".join(x for x in [cp.stdout.strip(), cp.stderr.strip()] if x)
    except Exception as exc:
        return f"flow_hook failed: {exc}"


def _stop_obligation_messages(project_root: Path) -> list[str]:
    state = _load_round_state(project_root)
    if not state:
        return []
    messages: list[str] = []
    current = _scratch_line_map(project_root)
    saved = state.get("scratch_map") or {}
    focus = _focus(project_root)
    topic_id = _focus_topic_id(focus)
    touched: list[dict[str, Any]] = []
    since = str(state.get("ts") or "")
    for path in [project_root / ".jiacong" / "round_touched.jsonl", project_root / ".claude" / ".round_touched.jsonl", STATE_DIR / "round_touched.jsonl"]:
        for row in _read_jsonl(path):
            if since and str(row.get("ts") or "") <= since:
                continue
            if str(row.get("project_root") or "") == str(project_root.resolve()) or str(row.get("project_root") or "") == str(project_root):
                touched.append(row)
    touched_topics = sorted({str(r.get("topic_id") or "") for r in touched if str(r.get("topic_id") or "")})
    if touched_topics:
        missing = [tid for tid in touched_topics if current.get(tid, 0) <= int(saved.get(tid, 0) or 0)]
        if missing:
            messages.append("[Jiacong Flow] Stop discipline: 本轮触达了话题文件，但对应 scratch 未新增记录：" + ", ".join(missing) + "。请先用 jiacong_flow_touch_scratch 或直接追加对应 topics/<id>/scratch.md。")
    elif topic_id and current.get(topic_id, 0) <= int(saved.get(topic_id, 0) or 0):
        messages.append(f"[Jiacong Flow] Stop discipline: 当前焦点 {topic_id} 的 scratch.md 本轮未新增记录；若本轮有实质判断/文件修改，应补写 scratch。")
    saved_focus = str(state.get("focus") or "")
    if saved_focus and focus and saved_focus != focus:
        if _stream_line_count(project_root) <= int(state.get("stream_lines") or 0):
            messages.append(f"[Jiacong Flow] Stop discipline: 焦点从 {saved_focus} 切到 {focus}，但 logs/stream.md 未新增签退/签到记录。")
    return messages


def _params_dict(params: Any) -> dict[str, Any]:
    if isinstance(params, dict):
        return params
    if isinstance(params, str):
        try:
            obj = json.loads(params) if params.strip() else {}
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _tool_base_cwd(kwargs: dict[str, Any], roots: compat.RootResolution) -> Path:
    cwd = compat.cwd_from_kwargs(kwargs)
    if cwd:
        try:
            return Path(cwd).expanduser().resolve()
        except Exception:
            return Path(cwd).expanduser()
    return roots.cwd


def _requested_project_cwd(params: dict[str, Any]) -> str | None:
    value = params.get("project_root")
    return value if isinstance(value, str) and value.strip() else None


def _confirmed_or_requested_root(roots: compat.RootResolution, requested: str | None, kwargs: dict[str, Any]) -> Path:
    if roots.project_root is not None:
        return roots.project_root
    fallback = requested or compat.cwd_from_kwargs(kwargs)
    if fallback:
        return Path(fallback).expanduser()
    return roots.cwd


def register(ctx) -> None:
    # Register skills via plugin mechanism (qualified name: jiacong-flow:smarter-project, etc.)
    if SMARTER.is_dir():
        skill_md = SMARTER / "SKILL.md"
        if skill_md.is_file():
            ctx.register_skill("smarter-project", skill_md, description="Jiacong Flow project governance discipline")
    if ONE_TURN.is_dir():
        skill_md = ONE_TURN / "SKILL.md"
        if skill_md.is_file():
            ctx.register_skill("one-turn-proposal", skill_md, description="One-turn proposal writing discipline")

    def on_session_start(**kwargs):
        roots = compat.resolve(kwargs)
        project_root = roots.project_root
        record = {
            "ts": datetime.now().isoformat(),
            "event": "on_session_start",
            "project_root": str(project_root) if project_root else "",
            "root_kind": roots.kind,
            "workspace_root": str(roots.workspace_root) if roots.workspace_root else "",
            "selected_project_root": str(roots.selected_worktree) if roots.selected_worktree else "",
            "selection": roots.selection,
            "reason": roots.reason,
            **kwargs,
        }
        if project_root:
            record["watcher"] = compat.ensure_watcher(project_root)
            try:
                report = _health_json(project_root)
                report_path = project_root / ".jiacong" / "session_report.json"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                record["health"] = {"warn_count": report.get("warn_count"), "ok": report.get("ok", True)}
            except Exception as exc:
                record["health_error"] = str(exc)
        _safe_write_jsonl(LOG_PATH, record)

    def pre_llm_call(**kwargs):
        roots = compat.resolve(kwargs)
        project_root = roots.project_root
        if not project_root:
            context = compat.build_pre_llm_context(
                roots,
                str(kwargs.get("user_message") or ""),
                is_first_turn=bool(kwargs.get("is_first_turn")),
            )
            return {"context": context} if context else None
        watcher = compat.ensure_watcher(project_root)
        context = compat.build_pre_llm_context(roots, str(kwargs.get("user_message") or ""))
        _safe_write_jsonl(LOG_PATH, {
            "ts": datetime.now().isoformat(),
            "event": "pre_llm_call",
            "project_root": str(project_root),
            "root_kind": roots.kind,
            "workspace_root": str(roots.workspace_root) if roots.workspace_root else "",
            "selected_project_root": str(roots.selected_worktree) if roots.selected_worktree else "",
            "selection": roots.selection,
            "reason": roots.reason,
            "session_id": kwargs.get("session_id"),
            "focus": _focus(project_root),
            "watcher": watcher,
        })
        return {"context": context}

    def post_tool_call(**kwargs):
        roots = compat.resolve(kwargs)
        project_root = roots.project_root
        tool_name = str(kwargs.get("tool_name") or kwargs.get("name") or "")
        args = kwargs.get("args") or kwargs.get("tool_input") or {}
        result = kwargs.get("result")
        touched_outputs: list[str] = []
        paths = _extract_paths_from_tool(tool_name, args, result, base_cwd=_tool_base_cwd(kwargs, roots))
        target_roots: set[str] = set()
        for path in paths:
            routed_root = compat.route_target(path)
            if routed_root is None:
                continue
            target_roots.add(str(routed_root.resolve()))
            _record_touched_file(routed_root, path, tool_name)
            if path.name in {"card.md", "scratch.md", "template.md"} and "topics" in path.parts:
                msg = _run_flow_hook_for_path(path)
                if msg:
                    touched_outputs.append(msg)
        record = {
            "ts": datetime.now().isoformat(),
            "event": "post_tool_call",
            "project_root": str(project_root) if project_root else "",
            "target_project_roots": sorted(target_roots),
            "tool_name": tool_name,
            "duration_ms": kwargs.get("duration_ms"),
            "paths": [str(p) for p in paths],
            "flow_hook_messages": touched_outputs[-5:],
        }
        _safe_write_jsonl(LOG_PATH, record)

    def transform_tool_result(**kwargs):
        # Surface flow_hook warnings in the tool result so the model can react in the same turn.
        roots = compat.resolve(kwargs)
        tool_name = str(kwargs.get("tool_name") or "")
        args = kwargs.get("args") or {}
        paths = _extract_paths_from_tool(tool_name, args, kwargs.get("result"), base_cwd=_tool_base_cwd(kwargs, roots))
        warnings: list[str] = []
        for path in paths:
            if compat.route_target(path) is None:
                continue
            if path.name in {"card.md", "scratch.md", "template.md"} and "topics" in path.parts:
                msg = _run_flow_hook_for_path(path)
                if msg:
                    warnings.append(msg)
        if not warnings:
            return None
        result = kwargs.get("result") or ""
        try:
            data = json.loads(result) if isinstance(result, str) else result
            if isinstance(data, dict):
                data.setdefault("jiacong_flow_warnings", warnings)
                return json.dumps(data, ensure_ascii=False)
        except Exception:
            pass
        return str(result) + "\n\n[Jiacong Flow warnings]\n" + "\n".join(warnings)

    def transform_llm_output(**kwargs):
        roots = compat.resolve(kwargs)
        project_root = roots.project_root
        if not project_root:
            return None
        messages = compat.stop_messages(roots)
        _safe_write_jsonl(LOG_PATH, {
            "ts": datetime.now().isoformat(),
            "event": "transform_llm_output",
            "project_root": str(project_root),
            "root_kind": roots.kind,
            "workspace_root": str(roots.workspace_root) if roots.workspace_root else "",
            "selection": roots.selection,
            "obligations": messages,
        })
        if not messages:
            return None
        response = str(kwargs.get("response_text") or "")
        footer = "\n\n---\n⚠️ **Jiacong Flow Stop discipline**\n" + "\n".join(f"- {m}" for m in messages)
        footer += "\n\n这不是内容错误，而是项目规约提醒：若本轮有实质推进，请先补写 scratch/log 后再结束。"
        return response.rstrip() + footer

    def on_session_end(**kwargs):
        roots = compat.resolve(kwargs)
        project_root = roots.project_root
        record = {
            "ts": datetime.now().isoformat(),
            "event": "on_session_end",
            "project_root": str(project_root) if project_root else "",
            "root_kind": roots.kind,
            "workspace_root": str(roots.workspace_root) if roots.workspace_root else "",
            "selection": roots.selection,
            **kwargs,
        }
        # Do not kill watcher every Telegram turn by default; it is cheap and belongs to project session.
        if os.environ.get("JIACONG_FLOW_STOP_WATCHER_ON_SESSION_END", "").lower() in {"1", "true", "yes"} and project_root:
            record["watcher_stop"] = compat.stop_watcher(project_root)
        _safe_write_jsonl(LOG_PATH, record)

    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_tool_call", post_tool_call)
    ctx.register_hook("transform_tool_result", transform_tool_result)
    ctx.register_hook("transform_llm_output", transform_llm_output)
    ctx.register_hook("on_session_end", on_session_end)

    health_schema = {"name": "jiacong_flow_health_check", "description": "Run Jiacong Flow smarter-project health_check.py for a managed project root.", "parameters": {"type": "object", "properties": {"project_root": {"type": "string", "description": "Project root. Defaults to nearest managed root from cwd."}}, "required": []}}
    def handle_health(params, **kwargs):
        params = _params_dict(params)
        requested = _requested_project_cwd(params)
        roots = compat.resolve(kwargs, cwd=requested)
        root = _confirmed_or_requested_root(roots, requested, kwargs)
        cp = _run_script("health_check.py", str(root), "--json", timeout=60)
        return json.dumps({"success": cp.returncode == 0, "project_root": str(root), "requested_path": requested or "", "root_kind": roots.kind, "selection": roots.selection, "stdout": cp.stdout, "stderr": cp.stderr, "returncode": cp.returncode}, ensure_ascii=False)

    focus_schema = {"name": "jiacong_flow_focus", "description": "Return Jiacong Flow focus breadcrumb for a managed project root.", "parameters": {"type": "object", "properties": {"project_root": {"type": "string", "description": "Project root. Defaults to nearest managed root from cwd."}}, "required": []}}
    def handle_focus(params, **kwargs):
        params = _params_dict(params)
        requested = _requested_project_cwd(params)
        roots = compat.resolve(kwargs, cwd=requested)
        root = _confirmed_or_requested_root(roots, requested, kwargs)
        focus = _focus(root)
        breadcrumb = _focus_breadcrumb(root)
        return json.dumps({
            "success": True,
            "project_root": str(root),
            "requested_path": requested or "",
            "root_kind": roots.kind,
            "selection": roots.selection,
            "focus": breadcrumb,
            "focus_value": focus,
            "focus_state": _focus_state(root),
        }, ensure_ascii=False)

    scratch_schema = {"name": "jiacong_flow_touch_scratch", "description": "Append a smarter-project formatted Sxxx update to the active Jiacong Flow topic scratch.md.", "parameters": {"type": "object", "properties": {"project_root": {"type": "string"}, "heading": {"type": "string"}, "text": {"type": "string"}}, "required": ["text"]}}
    def handle_scratch(params, **kwargs):
        params = _params_dict(params)
        requested = _requested_project_cwd(params)
        roots = compat.resolve(kwargs, cwd=requested)
        root = _confirmed_or_requested_root(roots, requested, kwargs)
        if roots.project_root is None:
            return json.dumps({
                "success": False,
                "project_root": str(root),
                "requested_path": requested or "",
                "root_kind": roots.kind,
                "selection": roots.selection,
                "error": "Jiacong Flow root is not confirmed; scratch writes require .jiacong/project.json confirmation",
            }, ensure_ascii=False)
        path = _append_scratch(root, params.get("text") or "", params.get("heading") or "Hermes update")
        return json.dumps({"success": True, "project_root": str(root), "requested_path": requested or "", "root_kind": roots.kind, "selection": roots.selection, "scratch": path}, ensure_ascii=False)

    watcher_schema = {"name": "jiacong_flow_watcher", "description": "Check/start/stop smarter-project watcher for a Jiacong Flow managed project.", "parameters": {"type": "object", "properties": {"project_root": {"type": "string"}, "action": {"type": "string", "enum": ["status", "start", "stop"]}}, "required": []}}
    def handle_watcher(params, **kwargs):
        params = _params_dict(params)
        requested = _requested_project_cwd(params)
        roots = compat.resolve(kwargs, cwd=requested)
        root = _confirmed_or_requested_root(roots, requested, kwargs)
        action = params.get("action") or "status"
        if roots.project_root is None:
            return json.dumps({
                "success": False,
                "project_root": str(root),
                "requested_path": requested or "",
                "root_kind": roots.kind,
                "selection": roots.selection,
                "error": "Jiacong Flow root is not confirmed; watcher requires .jiacong/project.json confirmation",
            }, ensure_ascii=False)
        if action == "start":
            return json.dumps({"success": True, "project_root": str(root), "requested_path": requested or "", "root_kind": roots.kind, "selection": roots.selection, "watcher": compat.ensure_watcher(root)}, ensure_ascii=False)
        if action == "stop":
            return json.dumps({"success": True, "project_root": str(root), "requested_path": requested or "", "root_kind": roots.kind, "selection": roots.selection, "watcher": compat.stop_watcher(root)}, ensure_ascii=False)
        status = compat.watcher_status(root)
        return json.dumps({"success": True, "project_root": str(root), "requested_path": requested or "", "root_kind": roots.kind, "selection": roots.selection, **status}, ensure_ascii=False)

    ctx.register_tool("jiacong_flow_health_check", toolset="jiacong_flow", schema=health_schema, handler=handle_health, description="Run Jiacong Flow project health check")
    ctx.register_tool("jiacong_flow_focus", toolset="jiacong_flow", schema=focus_schema, handler=handle_focus, description="Read Jiacong Flow active focus")
    ctx.register_tool("jiacong_flow_touch_scratch", toolset="jiacong_flow", schema=scratch_schema, handler=handle_scratch, description="Append to active topic scratch")
    ctx.register_tool("jiacong_flow_watcher", toolset="jiacong_flow", schema=watcher_schema, handler=handle_watcher, description="Manage smarter-project watcher")