# -*- coding: utf-8 -*-
"""CLI-specific hook output protocols."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable

from .agents import CODEX, GEMINI, hook_event_name, normalized_agent


class MessageBuffer:
    def __init__(self, *, prefix: str = "") -> None:
        self.prefix = prefix
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        if self.prefix:
            self.messages.append(f"{self.prefix}{message}")
        else:
            self.messages.append(message)

    def extend(self, messages: Iterable[str]) -> None:
        for message in messages:
            self.emit(message)

    def __len__(self) -> int:
        return len(self.messages)


def context_payload(
    agent: str,
    event_name: str,
    messages: Iterable[str],
    *,
    leading_newline: bool = False,
) -> dict:
    message_list = [message for message in messages if message]
    context = "\n".join(message_list)
    if leading_newline and context:
        context = "\n" + context

    agent_name = normalized_agent(["--agent", agent])
    event_name = hook_event_name(agent_name, event_name)

    output = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        },
    }
    if agent_name != CODEX:
        output["systemMessage"] = context
    return output


def write_context(
    agent: str,
    event_name: str,
    messages: Iterable[str],
    *,
    leading_newline: bool = False,
) -> None:
    message_list = [message for message in messages if message]
    if not message_list:
        return
    payload = context_payload(
        agent,
        event_name,
        message_list,
        leading_newline=leading_newline,
    )
    if not payload:
        return
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def codex_stop_payload(messages: Iterable[str]) -> dict:
    return {
        "decision": "block",
        "reason": "\n".join(message for message in messages if message),
    }


def gemini_stop_payload(messages: Iterable[str]) -> dict:
    reason = "\n".join(message for message in messages if message)
    return {
        "decision": "block",
        "reason": reason,
        "systemMessage": reason,
    }


def write_stop_block(agent: str, messages: Iterable[str]) -> int:
    message_list = [message for message in messages if message]
    if not message_list:
        return 0
    agent_name = normalized_agent(["--agent", agent])
    if agent_name == CODEX:
        sys.stdout.write(json.dumps(codex_stop_payload(message_list), ensure_ascii=False))
        sys.stdout.flush()
        return 0
    if agent_name == GEMINI:
        sys.stdout.write(json.dumps(gemini_stop_payload(message_list), ensure_ascii=False))
        sys.stdout.flush()
        return 0
    sys.stderr.write("\n".join(message_list))
    sys.stderr.flush()
    return 2
