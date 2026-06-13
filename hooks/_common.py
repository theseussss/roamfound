# -*- coding: utf-8 -*-
"""Deprecated compatibility surface for older hook imports.

New hook code should import from ``lib.*`` modules directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.agents import agent_arg, is_codex_agent, is_gemini_agent, normalized_agent
from lib.bridge import (
    PERSISTENCE_SIGNAL_PATTERNS,
    PROJECT_SIGNAL_PATTERNS,
    PROPOSAL_SIGNAL_PATTERNS,
    bridge_baseline_message,
    classify_route,
    routing_message,
)
from lib.debug import hook_debug
from lib.events import event_cwd, extract_user_prompt, read_hook_event, setup_encoding
from lib.roots import (
    ACTIVE_WORKTREE_FILES,
    WORKSPACE_STATE_DIR,
    RootResolution,
    find_hook_root,
    find_project_root,
    plugin_root,
    resolve_roots,
    state_dir,
)

__all__ = [
    "ACTIVE_WORKTREE_FILES",
    "PERSISTENCE_SIGNAL_PATTERNS",
    "PROJECT_SIGNAL_PATTERNS",
    "PROPOSAL_SIGNAL_PATTERNS",
    "RootResolution",
    "WORKSPACE_STATE_DIR",
    "agent_arg",
    "bridge_baseline_message",
    "classify_route",
    "event_cwd",
    "extract_user_prompt",
    "find_hook_root",
    "find_project_root",
    "hook_debug",
    "is_codex_agent",
    "is_gemini_agent",
    "normalized_agent",
    "plugin_root",
    "read_hook_event",
    "resolve_roots",
    "routing_message",
    "setup_encoding",
    "state_dir",
]
