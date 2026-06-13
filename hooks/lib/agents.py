# -*- coding: utf-8 -*-
"""CLI agent detection helpers."""

from __future__ import annotations

import sys


CLAUDE = "claude"
CODEX = "codex"
GEMINI = "gemini"

GEMINI_EVENT_MAP = {
    "UserPromptSubmit": "BeforeAgent",
    "PostToolUse": "AfterTool",
    "Stop": "AfterAgent",
}


def agent_arg(argv: list[str] | None = None) -> str:
    args = sys.argv[1:] if argv is None else argv
    for index, arg in enumerate(args):
        if arg == "--agent" and index + 1 < len(args):
            return args[index + 1].strip().lower()
        if arg.startswith("--agent="):
            return arg.split("=", 1)[1].strip().lower()
    return ""


def normalized_agent(argv: list[str] | None = None) -> str:
    value = agent_arg(argv)
    return value or CLAUDE


def is_codex_agent(argv: list[str] | None = None) -> bool:
    return agent_arg(argv) == CODEX


def is_gemini_agent(argv: list[str] | None = None) -> bool:
    return agent_arg(argv) == GEMINI


def hook_event_name(agent: str, event_name: str) -> str:
    if normalized_agent(["--agent", agent]) == GEMINI:
        return GEMINI_EVENT_MAP.get(event_name, event_name)
    return event_name
