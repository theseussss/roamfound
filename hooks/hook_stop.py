# -*- coding: utf-8 -*-
"""
Stop hook.

Checks lifecycle obligations after the assistant reply:
- scratch was updated for the active focus;
- log was updated if focus changed.

Claude blocks with stderr + exit 2. Codex blocks with native
``{"decision":"block","reason":"..."}`` JSON and exit 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.agents import normalized_agent
from lib.debug import hook_debug
from lib.events import event_cwd, read_hook_event, setup_encoding
from lib.output import codex_stop_payload, write_stop_block
from lib.roots import resolve_roots
from lib.round_state import load_round_state
from lib.scratch import stop_obligation_messages


_messages: list[str] = []


def _emit(message: str) -> None:
    _messages.append(f"[Jiacong Flow] {message}")


def _flush_codex_block() -> None:
    if not _messages:
        return
    import json

    sys.stdout.write(json.dumps(codex_stop_payload(_messages), ensure_ascii=False))
    sys.stdout.flush()


def main() -> None:
    _messages.clear()
    project_root: Path | None = None
    hook_root: Path | None = None
    agent = normalized_agent()
    setup_encoding()
    event = read_hook_event()

    try:
        roots = resolve_roots(event_cwd(event))
        hook_root = roots.hook_root
        hook_debug(
            "Stop",
            "start",
            hook_root=hook_root,
            details={
                "agent": agent,
                "root_kind": roots.kind,
                "stop_hook_active": event.get("stop_hook_active", False),
                "event_keys": sorted(event.keys()),
            },
        )

        if event.get("stop_hook_active", False):
            sys.exit(0)

        project_root = roots.project_root
        if project_root is None:
            sys.exit(0)
        if not (project_root / "topics").is_dir():
            sys.exit(0)

        state = load_round_state(project_root, roots)
        if state is None:
            sys.exit(0)

        for message in stop_obligation_messages(project_root, state):
            _emit(message)
    except Exception as exc:
        hook_debug(
            "Stop",
            "exception",
            project_root=project_root,
            hook_root=hook_root,
            exc=exc,
        )
        sys.exit(0)

    if _messages:
        hook_debug(
            "Stop",
            "block",
            project_root=project_root,
            hook_root=hook_root,
            details={"messages": len(_messages)},
        )
        sys.exit(write_stop_block(agent, _messages))

    hook_debug(
        "Stop",
        "exit",
        project_root=project_root,
        hook_root=hook_root,
        details={"messages": 0},
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
