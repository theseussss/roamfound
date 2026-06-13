# -*- coding: utf-8 -*-
"""
UserPromptSubmit hook.

Injects focus/stream discipline plus the peer-skill bridge reminder.
Never blocks the conversation; Stop enforces scratch/log obligations.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.agents import normalized_agent
from lib.bridge import bridge_baseline_message, classify_route, routing_message
from lib.debug import hook_debug
from lib.events import event_cwd, extract_user_prompt, read_hook_event, setup_encoding
from lib.focus import focus_messages, focus_topic_id, read_focus
from lib.messages import msg
from lib.output import MessageBuffer, write_context
from lib.roots import (
    plugin_root,
    project_context_message,
    resolve_roots,
    skill_dir,
    unmanaged_root_messages,
)
from lib.round_state import save_round_state
from lib.stream import stream_messages


_messages: list[str] = []


def _emit(message: str) -> None:
    _messages.append(f"[Jiacong Flow] {message}")


def _flush_output(event_name: str = "UserPromptSubmit") -> None:
    write_context(
        normalized_agent(),
        event_name,
        _messages,
        leading_newline=True,
    )


def main() -> None:
    project_root: Path | None = None
    hook_root: Path | None = None
    buffer = MessageBuffer(prefix="[Jiacong Flow] ")
    agent = normalized_agent()
    try:
        setup_encoding()
        event = read_hook_event()
        roots = resolve_roots(event_cwd(event))
        hook_root = roots.hook_root
        hook_debug(
            "UserPromptSubmit",
            "start",
            hook_root=hook_root,
            details={
                "agent": agent,
                "root_kind": roots.kind,
                "event_keys": sorted(event.keys()),
                "prompt_len": len(extract_user_prompt(event)),
            },
        )

        app_root = plugin_root(__file__)
        project_root = roots.project_root
        if project_root is None:
            buffer.extend(unmanaged_root_messages(roots, app_root))
            return
        if not (project_root / "topics").is_dir():
            return

        sp_skill = skill_dir(app_root)
        buffer.emit(project_context_message(roots, project_root))
        buffer.emit(msg("source.layer_classification"))
        buffer.extend(focus_messages(project_root, sp_skill))
        buffer.extend(stream_messages(project_root, sp_skill))
        buffer.emit(bridge_baseline_message())

        route = classify_route(extract_user_prompt(event))
        route_message = routing_message(route)
        if route_message:
            buffer.emit(route_message)

        focus_value = read_focus(project_root / ".claude" / "focus")
        if focus_value:
            save_round_state(project_root, focus_topic_id(focus_value), roots)
    except Exception as exc:
        hook_debug(
            "UserPromptSubmit",
            "exception",
            project_root=project_root,
            hook_root=hook_root,
            exc=exc,
        )
    finally:
        hook_debug(
            "UserPromptSubmit",
            "exit",
            project_root=project_root,
            hook_root=hook_root,
            details={"messages": len(buffer)},
        )
        write_context(agent, "UserPromptSubmit", buffer.messages, leading_newline=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
