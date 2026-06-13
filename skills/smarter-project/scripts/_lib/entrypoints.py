# -*- coding: utf-8 -*-
"""项目级多 CLI 入口契约。

`AGENTS.md` 是项目 canonical 入口；Claude、Gemini、Hermes 在项目根使用
各自 adapter 文件指向 `AGENTS.md`。`.claude/CLAUDE.md` 只作为 legacy
fallback 记录在机器契约中，不在新项目默认写出。
"""

from __future__ import annotations

import json
from pathlib import Path


SUPPORTED_ADAPTERS = {
    "claude": "CLAUDE.md",
    "gemini": "GEMINI.md",
    "hermes": "HERMES.md",
}


def entrypoints_payload() -> dict:
    return {
        "schema_version": "1",
        "generated_by": "jiacong-flow",
        "canonical": "AGENTS.md",
        "native": {
            "codex": "AGENTS.md",
        },
        "adapters": dict(SUPPORTED_ADAPTERS),
        "legacy": {
            "claude": ".claude/CLAUDE.md",
        },
    }


def _render_agents_entry_fallback(project_type: str = "general") -> str:
    project_line = f"- 项目类型：`{project_type}`。" if project_type else "- 项目类型：未指定。"
    return f"""# Jiacong Flow Project Entry

This `AGENTS.md` is the canonical project entry for Jiacong Flow / smarter-project.

## Project contract

{project_line}
- Canonical entry: `AGENTS.md`.
- Project metadata: `.jiacong/project.json`.
- Current focus state: `.jiacong/focus.json`.
- Topic knowledge base: `topics/`.
- Lifecycle stream: `logs/stream.md`.

## CLI adapters

- Codex reads this file natively as its project entry.
- Claude Code should enter through root `CLAUDE.md`, which points back to this file.
- Gemini should enter through root `GEMINI.md`, which points back to this file.
- Hermes should enter through root `HERMES.md`, which points back to this file.

## Legacy compatibility

`.claude/CLAUDE.md` is a legacy fallback for older projects or Claude-specific
compatibility. It is not the canonical project entry for new Jiacong Flow projects.
"""


def render_agents_entry(project_type: str = "general") -> str:
    return _render_agents_entry_fallback(project_type)


def render_cli_adapter(agent: str) -> str:
    normalized = agent.lower().strip()
    if normalized not in SUPPORTED_ADAPTERS:
        raise ValueError(f"unsupported adapter: {agent}")
    display = {
        "claude": "Claude Code",
        "gemini": "Gemini CLI",
        "hermes": "Hermes Agent",
    }[normalized]
    return f"""# Jiacong Flow · {display} adapter

This file is an adapter. The canonical project entry is `AGENTS.md`.

Read and follow `AGENTS.md` first. Do not treat `.claude/CLAUDE.md` as the
project's main entry unless you are explicitly handling a legacy fallback case.
"""


def write_project_entrypoints(
    project_root: Path | str,
    project_type: str = "general",
    agents_entry: str | None = None,
) -> dict:
    root = Path(project_root)
    payload = entrypoints_payload()

    root.mkdir(parents=True, exist_ok=True)
    (root / ".jiacong").mkdir(parents=True, exist_ok=True)

    (root / "AGENTS.md").write_text(
        agents_entry if agents_entry is not None else render_agents_entry(project_type),
        encoding="utf-8",
    )
    for agent, rel_path in payload["adapters"].items():
        (root / rel_path).write_text(render_cli_adapter(agent), encoding="utf-8")

    (root / ".jiacong" / "entrypoints.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload
