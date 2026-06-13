# -*- coding: utf-8 -*-
"""Bridge routing between smarter-project and one-turn-proposal."""

from __future__ import annotations

import re
from typing import Any

from .messages import msg


PROJECT_SIGNAL_PATTERNS = (
    r"建档",
    r"话题",
    r"scratch",
    r"card",
    r"tasks?",
    r"焦点",
    r"流水",
    r"归档",
    r"分支",
    r"合并",
    r"commit",
    r"git",
    r"worktree",
    r"项目",
    r"project",
    r"topic",
    r"focus",
    r"branch",
    r"merge",
)

PROPOSAL_SIGNAL_PATTERNS = (
    r"提案",
    r"方案",
    r"架构",
    r"框架",
    r"方法论",
    r"策略",
    r"路线图",
    r"协议",
    r"综述",
    r"证据",
    r"来源",
    r"审查",
    r"检索",
    r"决策",
    r"比较",
    r"权衡",
    r"PRD",
    r"RFC",
    r"ADR",
    r"schema",
    r"eval",
    r"agent",
    r"plugin",
    r"skill",
    r"bridge",
    r"routing",
    r"路由",
    r"命中",
    r"proposal",
    r"architecture",
    r"methodology",
    r"evidence",
    r"review",
    r"decision",
    r"compare",
    r"trade-?off",
)

PERSISTENCE_SIGNAL_PATTERNS = (
    r"记录",
    r"补充",
    r"写入",
    r"回写",
    r"沉淀",
    r"提炼",
    r"补到\s*scratch",
    r"补\s*scratch",
    r"拆\s*tasks?",
    r"更新\s*card",
    r"persist",
    r"record",
    r"write",
    r"scratch",
    r"tasks?",
)


def classify_route(prompt: str) -> dict[str, Any]:
    text = prompt.strip()
    lowered = text.lower()
    explicit_smarter = "smarter-project" in lowered or "smarter project" in lowered
    explicit_proposal = "one-turn-proposal" in lowered or "one turn proposal" in lowered

    project = explicit_smarter or _matches_any(text, PROJECT_SIGNAL_PATTERNS)
    proposal = explicit_proposal or _matches_any(text, PROPOSAL_SIGNAL_PATTERNS)
    persistence = _matches_any(text, PERSISTENCE_SIGNAL_PATTERNS)

    if explicit_smarter and explicit_proposal:
        route = "composite"
    elif explicit_proposal and (project or persistence):
        route = "composite"
    elif explicit_smarter:
        route = "smarter-project"
    elif explicit_proposal:
        route = "one-turn-proposal"
    elif proposal and (project or persistence):
        route = "composite"
    elif project or persistence:
        route = "smarter-project"
    elif proposal:
        route = "one-turn-proposal"
    else:
        route = "none"

    return {
        "route": route,
        "project_signal": project,
        "proposal_signal": proposal,
        "persistence_signal": persistence,
        "explicit_smarter": explicit_smarter,
        "explicit_proposal": explicit_proposal,
    }


def bridge_baseline_message() -> str:
    return msg("bridge.baseline")


def routing_message(route: dict[str, Any]) -> str:
    name = route.get("route", "none")
    if name == "composite":
        return msg("bridge.signal.composite")
    if name == "smarter-project":
        return msg("bridge.signal.project")
    if name == "one-turn-proposal":
        return msg("bridge.signal.proposal")
    return ""


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
