# -*- coding: utf-8 -*-
"""Hook event input and prompt extraction helpers."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any


def setup_encoding() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def read_hook_event(
    timeout: float = 2.0,
    *,
    debug_copy_path: Path | None = None,
) -> dict[str, Any]:
    result: list[bytes | str | None] = [None]

    def _reader() -> None:
        try:
            stream = getattr(sys.stdin, "buffer", sys.stdin)
            result[0] = stream.read()
        except Exception:
            pass

    try:
        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        t.join(timeout=timeout)
    except Exception:
        return {}

    raw_value = result[0] or b""
    if isinstance(raw_value, bytes):
        raw = _decode_bytes(raw_value).strip()
    else:
        raw = raw_value.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if debug_copy_path is not None:
            _write_debug_copy(debug_copy_path, parsed)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _decode_bytes(value: bytes) -> str:
    for encoding in ("utf-8", getattr(sys.stdin, "encoding", "") or "", "gbk"):
        if not encoding:
            continue
        try:
            return value.decode(encoding)
        except Exception:
            pass
    return value.decode("utf-8", errors="replace")


def _write_debug_copy(path: Path, parsed: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def event_cwd(event: dict[str, Any]) -> str | None:
    value = event.get("cwd")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def extract_user_prompt(event: dict[str, Any]) -> str:
    gemini_prompt = _extract_last_user_message(event)
    if gemini_prompt:
        return gemini_prompt[:2000]

    for key_path in (
        ("prompt",),
        ("user_prompt",),
        ("userPrompt",),
        ("message", "content"),
        ("message", "text"),
        ("input",),
        ("text",),
        ("content",),
    ):
        value = _get_nested_string(event, key_path)
        if value:
            return value[:2000]

    candidates: list[str] = []
    _collect_prompt_candidates(event, candidates, depth=0)
    candidates = [item.strip() for item in candidates if item and item.strip()]
    if not candidates:
        return ""
    return max(candidates, key=len)[:2000]


def _extract_last_user_message(event: dict[str, Any]) -> str:
    messages = event.get("llm_request", {}).get("messages")
    if not isinstance(messages, list):
        return ""

    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).lower()
        if role != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            joined = "\n".join(part.strip() for part in parts if part and part.strip())
            if joined:
                return joined
    return ""


def _get_nested_string(value: Any, key_path: tuple[str, ...]) -> str:
    current = value
    for key in key_path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current.strip() if isinstance(current, str) else ""


def _collect_prompt_candidates(value: Any, out: list[str], depth: int) -> None:
    if depth > 5:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if isinstance(child, str) and lowered in {
                "prompt",
                "user_prompt",
                "userprompt",
                "input",
                "message",
                "text",
                "content",
            }:
                out.append(child)
            else:
                _collect_prompt_candidates(child, out, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _collect_prompt_candidates(child, out, depth + 1)
    elif isinstance(value, str) and depth <= 2:
        out.append(value)
