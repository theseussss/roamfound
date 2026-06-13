# -*- coding: utf-8 -*-
"""Jiacong Flow 项目路径契约。

本模块只表达“某类项目状态应落到哪里”，不做任何 IO。默认路径指向
``.jiacong/``；旧 ``.claude/`` 路径只能通过 ``legacy_*`` 函数显式取得。
"""

from __future__ import annotations

from pathlib import Path

WORKSPACE_STATE_DIR = ".jiacong-workspace"


def _root(project_root: Path | str) -> Path:
    return Path(project_root)


# metadata / contract

def jiacong_dir(project_root: Path | str) -> Path:
    return _root(project_root) / ".jiacong"


def project_marker_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "project.json"


def entrypoints_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "entrypoints.json"


# current state

def focus_state_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "focus.json"


def round_state_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "round_state.json"


def round_touched_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "round_touched.jsonl"


# runtime process artifacts

def watcher_pid_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "watcher.pid"


def watcher_metadata_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "watcher.json"


def watcher_log_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "watcher.log"


def hook_debug_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "hook_debug.log"


def session_report_path(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "session_report.json"


# generated / cache

def dashboard_dir(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "dashboard"


def dashboard_index_path(project_root: Path | str) -> Path:
    return dashboard_dir(project_root) / "index.html"


def dashboard_state_path(project_root: Path | str) -> Path:
    return dashboard_dir(project_root) / "state.json"


def role_manager_path(project_root: Path | str) -> Path:
    return dashboard_dir(project_root) / "role_manager.html"


def cache_dir(project_root: Path | str) -> Path:
    return jiacong_dir(project_root) / "cache"


def card_edits_path(project_root: Path | str) -> Path:
    return cache_dir(project_root) / "card-edits.jsonl"


# legacy fallback only

def legacy_state_dir(project_root: Path | str) -> Path:
    return _root(project_root) / ".claude"


def legacy_focus_path(project_root: Path | str) -> Path:
    return legacy_state_dir(project_root) / "focus"


def legacy_round_state_path(project_root: Path | str) -> Path:
    return legacy_state_dir(project_root) / ".round_state.json"


def legacy_round_touched_path(project_root: Path | str) -> Path:
    return legacy_state_dir(project_root) / ".round_touched.jsonl"


def legacy_hook_debug_path(project_root: Path | str) -> Path:
    return legacy_state_dir(project_root) / "hook_debug.log"


def legacy_session_report_path(project_root: Path | str) -> Path:
    return legacy_state_dir(project_root) / "session_report.json"


def legacy_dashboard_path(project_root: Path | str) -> Path:
    return legacy_state_dir(project_root) / "dashboard.html"


def legacy_watcher_pid_path(project_root: Path | str) -> Path:
    return legacy_state_dir(project_root) / "watcher.pid"
