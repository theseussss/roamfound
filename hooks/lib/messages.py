# -*- coding: utf-8 -*-
"""Load and render hook-visible message templates."""

from __future__ import annotations

import ast
import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


MESSAGES_PATH = Path(__file__).resolve().parents[1] / "messages.yaml"
_CACHE: dict[str, dict[str, Any]] | None = None


class MessageText(str):
    """Rendered hook text with its message metadata kept beside the text."""

    message_id: str
    meta: dict[str, Any]

    def __new__(cls, value: str, message_id: str = "", meta: dict[str, Any] | None = None):
        obj = str.__new__(cls, value)
        obj.message_id = message_id
        obj.meta = dict(meta or {})
        return obj

    def __add__(self, other: object) -> "MessageText":
        return MessageText(str(self) + str(other), self.message_id, self.meta)

    def __radd__(self, other: object) -> "MessageText":
        return MessageText(str(other) + str(self), self.message_id, self.meta)


def load_messages(path: Path = MESSAGES_PATH) -> dict[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        data = json.loads(text)
        return _flatten_json_messages(data)
    return _parse_simple_yaml_messages(text)


def clear_cache() -> None:
    global _CACHE
    _CACHE = None


def _runtime_message_values() -> dict[str, object]:
    # 项目名不在 hook 提示里实例化：未绑定项目根时无项目名可填，
    # 系统署名 Jiacong Flow 直接写死在模板中。此处只提供每轮运行事实。
    now = datetime.now().astimezone()
    timezone = now.tzname() or ""
    return {
        "local_datetime": f"{now.strftime('%Y-%m-%d %H:%M:%S')} {timezone}".strip(),
        "local_date": now.strftime("%Y-%m-%d"),
        "local_time": now.strftime("%H:%M:%S"),
        "timezone": timezone,
    }


def msg(message_id: str, **values: object) -> MessageText:
    global _CACHE
    if _CACHE is None:
        _CACHE = load_messages()
    spec = _CACHE.get(message_id)
    if spec is None:
        return MessageText(f"[missing message:{message_id}]", message_id, _default_meta(message_id))
    template = str(spec.get("text") or "")
    meta = _message_meta(message_id, spec)
    try:
        merged = _runtime_message_values()
        merged.update(values)
        return MessageText(template.format(**merged), message_id, meta)
    except KeyError as exc:
        return MessageText(f"{template} [missing variable:{exc.args[0]}]", message_id, meta)
    except Exception as exc:
        return MessageText(f"{template} [render error:{type(exc).__name__}]", message_id, meta)


def runtime_boundary_xml(
    messages: list[object] | tuple[object, ...],
    *,
    lifecycle: str = "pre_llm_call",
    source: str = "jiacong-flow-hook",
    schema: str = "jiacong-flow.system_hook_prompt.v1",
    persistence: str = "ephemeral",
) -> str:
    """Render Hermes hook context as one XML system hook prompt.

    Hermes pre_llm_call can only inject text near the user message. This wrapper
    makes every injected item explicitly system-hook-owned while preserving its text.
    """
    items = [message for message in messages if str(message)]
    if not items:
        return ""

    lines = [
        (
            f'<system_hook_prompt schema="{html.escape(schema, quote=True)}" '
            f'sender="hook" source="{html.escape(source, quote=True)}" '
            'not_user_message="true" visibility="do_not_answer" '
            'treat_as="system_hook_prompt" '
            f'lifecycle="{html.escape(lifecycle, quote=True)}" '
            f'persistence="{html.escape(persistence, quote=True)}">'
        ),
        (
            '<system_hook_prompt_rule sender="hook" not_user_message="true" preserve_text="true">'
            "红线规则：本 system_hook_prompt 由系统 hook 自动生成，是 system hook prompt，绝不是用户消息。"
            "真实用户消息只在 system_hook_prompt 外部。"
            "禁止回应本段，禁止总结本段，禁止引用本段，禁止复述本段，禁止把本段当作‘上一段’‘上面那段’或用户粘贴的内容。"
            "禁止声明已收到本段、已遵循本段、不会回应本段，也禁止围绕本段发表任何说明。"
            "即使真实用户消息为空、极短、只有语气词、符号或没有实质性回复，也不得把本段当作输入对象；按真实用户消息本身回应，必要时保持简短或询问澄清。"
            "任何情况下都不得主动提及、引用、解释、总结或暗示存在本 system_hook_prompt；只能将其作为系统内部运行消息处理。"
            "除非用户显式点名 system_hook_prompt、hook、系统提示或运行注入并要求讨论，才可在必要范围内说明。"
            "若用户要求处理‘上一段/上面那段’，默认指向 system_hook_prompt 外部最近一条真实用户消息或 assistant 消息，不得指向本段。"
            "如用户显式要求讨论本段，只能表述为‘系统提示到……’或‘system hook prompt 提示到……’，禁止说‘用户贴的这段……’‘你贴出的这段……’或任何把本段归属于用户的说法。"
            "</system_hook_prompt_rule>"
        ),
        "<system_hook_prompt_items>",
    ]
    for idx, item in enumerate(items):
        lines.append(hook_item_xml(item, default_id=f"system_hook_prompt.item.{idx:02d}"))
    lines.append("</system_hook_prompt_items>")
    lines.append("</system_hook_prompt>")
    return "\n".join(lines)


def hook_item_xml(
    message: object,
    *,
    default_id: str = "hook.item",
    meta: dict[str, Any] | None = None,
) -> str:
    """Render one hook message as a structured item while preserving its text."""
    text = str(message)
    message_id = getattr(message, "message_id", "") or default_id
    base_meta = _message_meta(message_id, getattr(message, "meta", {}) or {})
    if meta:
        base_meta.update({k: v for k, v in meta.items() if v is not None})
    base_meta.setdefault("sender", "hook")
    base_meta.setdefault("source", "jiacong-flow-hook")
    base_meta.setdefault("not_user_message", True)
    base_meta.setdefault("preserve_text", True)
    base_meta.setdefault("response_policy", "do_not_answer")

    attrs = {"id": message_id}
    for key in (
        "sender",
        "source",
        "not_user_message",
        "layer",
        "category",
        "audience",
        "response_policy",
        "requires_action",
        "action_type",
        "preserve_text",
    ):
        if key in base_meta and base_meta[key] not in (None, ""):
            attrs[key] = _xml_attr_value(base_meta[key])

    attr_text = " ".join(f'{name}="{html.escape(str(value), quote=True)}"' for name, value in attrs.items())
    return f"<system_hook_prompt_item {attr_text}>\n<text><![CDATA[\n{_cdata(text)}\n]]></text>\n</system_hook_prompt_item>"


def _flatten_json_messages(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            result[str(key)] = dict(value)
        elif isinstance(value, str):
            result[str(key)] = {"text": value}
    return result


def _parse_simple_yaml_messages(text: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    current: str | None = None
    block_key: str | None = None
    block_lines: list[str] = []

    def ensure_current() -> dict[str, Any]:
        if current is None:
            return {}
        return result.setdefault(current, {})

    def flush_block() -> None:
        nonlocal block_key, block_lines
        if current and block_key == "text":
            ensure_current()["text"] = "\n".join(block_lines).rstrip("\n")
        block_key = None
        block_lines = []

    for raw_line in text.splitlines():
        if block_key is not None:
            if not raw_line.strip():
                block_lines.append("")
                continue
            if raw_line.startswith("    "):
                block_lines.append(raw_line[4:])
                continue
            flush_block()

        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not raw_line.startswith((" ", "\t")) and stripped.endswith(":"):
            current = stripped[:-1]
            result.setdefault(current, {})
            continue

        if current is None or not raw_line.startswith("  "):
            continue

        field, sep, value = stripped.partition(":")
        if sep != ":":
            continue
        value = value.strip()
        if field == "text" and value == "|":
            block_key = "text"
            block_lines = []
        else:
            ensure_current()[field] = _decode_scalar(value)

    flush_block()
    return result


def _decode_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            decoded = ast.literal_eval(value)
            return decoded if isinstance(decoded, str) else str(decoded)
        except Exception:
            return value[1:-1]
    return value


def _message_meta(message_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    meta = _default_meta(message_id)
    for key, value in spec.items():
        if key != "text":
            meta[key] = value
    return meta


def _default_meta(message_id: str) -> dict[str, Any]:
    layer = "runtime_context"
    category = message_id.replace(".", "_") or "message"
    response_policy = "do_not_answer"
    requires_action = False
    action_type = ""

    if message_id.startswith("context."):
        layer = "project_context"
        response_policy = "use_for_project_state"
    elif message_id.startswith("focus.breadcrumb") or message_id.startswith("focus.not_found") or message_id.startswith("focus.missing"):
        layer = "focus_state"
        response_policy = "use_for_routing"
    elif message_id.startswith("focus.classify"):
        layer = "routing_policy"
        response_policy = "use_for_routing"
        requires_action = message_id.endswith("required")
        action_type = "classify_focus" if requires_action else ""
    elif message_id.startswith("stream."):
        layer = "stream_state"
        response_policy = "use_for_obligation_check"
        requires_action = True
        action_type = "record_stream_or_scratch"
    elif message_id.startswith("bridge."):
        layer = "bridge_state"
        response_policy = "use_for_project_state"
    elif message_id.startswith("root.") or message_id.startswith("session.") or message_id.startswith("auto."):
        layer = "root_boundary"
        response_policy = "use_for_project_state"
    elif message_id.startswith("stop."):
        layer = "stop_obligation"
        response_policy = "use_for_obligation_check"
        requires_action = True
        action_type = "satisfy_stop_obligation"
    elif message_id.startswith("diagnostic."):
        layer = "diagnostic"
        response_policy = "diagnostic_only"

    return {
        "sender": "hook",
        "source": "jiacong-flow-hook",
        "not_user_message": True,
        "layer": layer,
        "category": category,
        "audience": "assistant_runtime",
        "response_policy": response_policy,
        "requires_action": requires_action,
        "action_type": action_type,
        "preserve_text": True,
    }


def _xml_attr_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _cdata(text: str) -> str:
    return text.replace("]]>", "]]]]><![CDATA[>")
