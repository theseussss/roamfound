# -*- coding: utf-8 -*-
"""Project/workspace root resolution for hooks."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .messages import msg


WORKSPACE_STATE_DIR = ".jiacong-workspace"
ACTIVE_WORKTREE_FILES = ("current-worktree", "active-worktree", "current-root")
CONFIRM_MARKER = Path(".jiacong") / "project.json"
LEGACY_TRACE_PATHS = (
    ".claude",
    "topics",
    "logs",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "SOUL.md",
)
PROJECT_CONFIG_FILES = (
    "package.json",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "Gemfile",
    "composer.json",
)
README_FILES = ("README.md", "README.rst", "README.txt")
SOURCE_DIRS = ("src", "app", "lib", "pkg", "packages", "apps")


@dataclass(frozen=True)
class MarkerAudit:
    status: str
    path: Path
    project_root: Path | None = None
    reason: str = ""

    @property
    def valid(self) -> bool:
        return self.status == "valid_confirmed"


@dataclass(frozen=True)
class StructureFeatures:
    has_git: bool = False
    has_repo_git: bool = False
    has_main: bool = False
    has_worktrees: bool = False
    project_configs: tuple[str, ...] = ()
    has_readme: bool = False
    source_dirs: tuple[str, ...] = ()


@dataclass(frozen=True)
class LayerScan:
    path: Path
    marker: MarkerAudit
    legacy_traces: tuple[str, ...] = ()
    jiacong_legacy_traces: tuple[str, ...] = ()
    agent_ecosystem_traces: tuple[str, ...] = ()
    structure: StructureFeatures = field(default_factory=StructureFeatures)
    is_home: bool = False
    is_root: bool = False
    is_shallow_mount: bool = False
    is_special_dir: str | None = None
    scan_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChildScan:
    name: str
    path: Path
    marker: MarkerAudit
    legacy_traces: tuple[str, ...]
    structure: StructureFeatures
    scan_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanResult:
    cwd: Path
    parent: Path
    dirname: str
    cwd_source: str
    cwd_confidence: str
    current: LayerScan
    parent_layer: LayerScan
    children: tuple[ChildScan, ...] = ()
    scan_errors: tuple[str, ...] = ()

    @property
    def confirmed_children(self) -> tuple[ChildScan, ...]:
        return tuple(child for child in self.children if child.marker.valid)


@dataclass(frozen=True)
class SourceResolution:
    configured: bool
    source_root: Path | None = None
    main_worktree: Path | None = None
    worktrees_root: Path | None = None
    source_dir: str = ""
    git_enabled: bool = False
    reason: str = ""


@dataclass(frozen=True)
class RootResolution:
    kind: str
    cwd: Path
    project_root: Path | None = None
    hook_root: Path | None = None
    workspace_root: Path | None = None
    selected_worktree: Path | None = None
    candidate_root: Path | None = None
    selection: str = ""
    reason: str = ""
    scan: ScanResult | None = None

    @property
    def is_managed(self) -> bool:
        return self.project_root is not None

    @property
    def is_workspace(self) -> bool:
        return self.workspace_root is not None


def resolve_roots(cwd: str | Path | None = None) -> RootResolution:
    current = _resolve_current(cwd)
    scan = scan_three_layers(current)

    # 硬性风险优先。语义是“当前目录本身不能作为项目根”，不是禁止提示子目录。
    risk_kind = _hard_risk_kind(scan.current)
    if risk_kind:
        return RootResolution(
            kind=risk_kind,
            cwd=current,
            hook_root=current if current.is_dir() else current.parent,
            candidate_root=current if current.is_dir() else current.parent,
            reason=f"hard risk location: {risk_kind}",
            scan=scan,
        )

    # 有效确认标记是唯一授权依据。当前层优先。
    if scan.current.marker.valid:
        return RootResolution(
            kind="confirmed_root",
            cwd=current,
            project_root=scan.current.path,
            hook_root=scan.current.path,
            candidate_root=scan.current.path,
            reason="valid .jiacong/project.json confirmation found at cwd",
            scan=scan,
        )

    # 已初始化 workspace 的显式 selection 是运行状态，不是扫描分类。
    # 只有 selection 指向有效确认项目根时才授权路由。
    explicit_workspace = _explicit_workspace_selection(current)
    if explicit_workspace is not None:
        workspace_root, selected_root, selection = explicit_workspace
        return RootResolution(
            kind="workspace_selected_managed",
            cwd=current,
            project_root=selected_root,
            hook_root=workspace_root,
            workspace_root=workspace_root,
            selected_worktree=selected_root,
            candidate_root=selected_root,
            selection=selection,
            reason="explicit workspace selection routes to confirmed project root",
            scan=scan,
        )

    # 当前层有容器结构线索时，不向上继承父项目授权；它需要 AI/用户确认或显式 selection。
    if scan.current.structure.has_repo_git and (scan.current.structure.has_main or scan.current.structure.has_worktrees):
        return RootResolution(
            kind="needs_ai_judgment",
            cwd=current,
            hook_root=current,
            candidate_root=current,
            reason="container-like structure requires AI/user judgment; parent confirmation is not inherited",
            scan=scan,
        )

    # 最近有效祖先确认标记表示当前目录是项目子目录。授权搜索仍受 Home/根/浅层挂载边界约束。
    ancestor = _nearest_confirmed_ancestor(current)
    if ancestor is not None:
        return RootResolution(
            kind="confirmed_subdir",
            cwd=current,
            project_root=ancestor,
            hook_root=ancestor,
            candidate_root=ancestor,
            reason="valid .jiacong/project.json confirmation found at ancestor",
            scan=scan,
        )

    return RootResolution(
        kind="needs_ai_judgment",
        cwd=current,
        hook_root=current if current.is_dir() else current.parent,
        candidate_root=current if current.is_dir() else current.parent,
        reason="no confirmed project marker found; facts injected for AI judgment",
        scan=scan,
    )


def scan_three_layers(current: Path) -> ScanResult:
    errors: list[str] = []
    parent = current.parent if current.parent != current else current
    current_layer = _scan_layer(current)
    parent_layer = _scan_layer(parent)
    children = _scan_children(current, errors)
    return ScanResult(
        cwd=current,
        parent=parent,
        dirname=current.name,
        cwd_source=_cwd_source(),
        cwd_confidence=_cwd_confidence(_cwd_source()),
        current=current_layer,
        parent_layer=parent_layer,
        children=tuple(children),
        scan_errors=tuple(errors),
    )


def _explicit_workspace_selection(current: Path) -> tuple[Path, Path, str] | None:
    # 这不是扫描分类；只有显式运行状态存在且目标已确认时才授权。
    for workspace in (current, *current.parents):
        state_dir_path = workspace / WORKSPACE_STATE_DIR
        if not state_dir_path.is_dir():
            continue
        for file_name in ACTIVE_WORKTREE_FILES:
            path = state_dir_path / file_name
            if not path.is_file():
                continue
            selection = _read_first_value(path)
            if not selection:
                continue
            selected = _resolve_selection(workspace, selection)
            if selected is None:
                continue
            if audit_confirm_marker(selected).valid:
                return workspace, selected, selection
    return None


def _read_first_value(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                return value
    except Exception:
        pass
    return ""


def _resolve_selection(workspace: Path, selection: str) -> Path | None:
    raw = selection.strip().strip('"').strip("'")
    if not raw:
        return None

    direct = _resolve_selection_path(workspace, raw)
    if direct is not None:
        return direct

    return _resolve_selection_from_git_worktrees(workspace, raw)


def _resolve_selection_path(workspace: Path, raw: str) -> Path | None:
    """把 selection 当作路径解析；支持容器内相对路径、外部绝对路径和 Windows 盘符路径。"""
    try:
        candidate = _selection_candidate_path(workspace, raw)
        candidate = candidate.expanduser().resolve()
        if not candidate.is_dir():
            return None
        workspace_resolved = workspace.resolve()
        nested = _nearest_git_root(candidate, workspace_resolved)
        return nested or candidate
    except Exception:
        return None


def _selection_candidate_path(workspace: Path, raw: str) -> Path:
    candidate = _normalize_platform_path(Path(raw))
    if not candidate.is_absolute():
        candidate = workspace / candidate
    return candidate


def _resolve_selection_from_git_worktrees(workspace: Path, raw: str) -> Path | None:
    """用 Git worktree 元数据把 branch/rel/path selection 解析成真实 worktree。"""
    for item in _git_worktrees(workspace):
        if _selection_matches_worktree(workspace, raw, item):
            return item
    return None


def _git_worktrees(workspace: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "--git-dir", str(workspace / ".repo.git"), "worktree", "list", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    paths: list[Path] = []
    current: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            _append_worktree_entry(paths, current)
            current = {}
            continue
        if line.startswith("worktree "):
            _append_worktree_entry(paths, current)
            current = {"path": line[len("worktree ") :]}
        elif line.startswith("branch "):
            branch = line[len("branch ") :]
            if branch.startswith("refs/heads/"):
                branch = branch[len("refs/heads/") :]
            current["branch"] = branch
        elif line == "bare":
            current["bare"] = "1"
    _append_worktree_entry(paths, current)
    return paths


def _append_worktree_entry(paths: list[Path], entry: dict[str, str]) -> None:
    if not entry or entry.get("bare"):
        return
    raw_path = entry.get("path")
    if not raw_path:
        return
    try:
        path = _normalize_platform_path(Path(raw_path)).expanduser().resolve()
    except Exception:
        path = _normalize_platform_path(Path(raw_path))
    if path.is_dir():
        paths.append(path)


def _selection_matches_worktree(workspace: Path, raw: str, worktree: Path) -> bool:
    raw_norm = _path_text(raw)
    try:
        rel = _path_text(worktree.resolve().relative_to(workspace.resolve()))
    except Exception:
        rel = ""
    names = {
        worktree.name,
        _git_branch(worktree),
        _path_text(worktree),
        _path_text(worktree.resolve()),
    }
    if rel:
        names.add(rel)
    candidate = _resolve_selection_path(workspace, raw)
    if candidate is not None:
        names.add(_path_text(candidate))
        try:
            names.add(_path_text(candidate.resolve()))
        except Exception:
            pass
    return raw_norm in {value for value in names if value}


def _git_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _normalize_platform_path(path: Path) -> Path:
    text = str(path)
    if len(text) >= 3 and text[1:3] in {":/", ":\\"} and text[0].isalpha():
        drive = text[0].lower()
        rest = text[3:].replace("\\", "/")
        return Path("/mnt") / drive / rest
    return path


def _path_text(value: object) -> str:
    return str(value).replace("\\", "/").rstrip("/")


def _nearest_git_root(candidate: Path, stop_at: Path) -> Path | None:
    for path in (candidate, *candidate.parents):
        if path == stop_at:
            break
        if (path / ".git").exists():
            return path
    return None


def _nearest_confirmed_ancestor(path: Path) -> Path | None:
    for candidate in path.parents:
        layer = _scan_layer(candidate)
        if _hard_risk_kind(layer):
            return None
        if layer.marker.valid and _is_relative_to(path, candidate):
            return candidate
    return None


def route_target(target: str | Path) -> Path | None:
    """解析某个动作目标（文件/目录）归属哪个已确认项目根。

    从目标向上找最近的有效 .jiacong/project.json；遇到硬性风险边界
    （Home/文件系统根/浅层挂载）即停并返回 None。按动作目标路由，
    与会话 cwd 无关：人在 Home 改某项目文件时，动作仍归属该项目。
    """
    try:
        resolved = Path(target).expanduser().resolve()
    except Exception:
        return None
    try:
        start = resolved if resolved.is_dir() else resolved.parent
    except Exception:
        start = resolved.parent
    for candidate in (start, *start.parents):
        layer = _scan_layer(candidate)
        if _hard_risk_kind(layer):
            return None
        if layer.marker.valid:
            return candidate
    return None


def find_project_root() -> Path | None:
    return resolve_roots().project_root


def find_hook_root() -> Path | None:
    return resolve_roots().hook_root


def resolve_source(project_root: Path | None) -> SourceResolution:
    """从已确认管理根读取源码层布局；不维护当前源码 worktree 指针。"""
    if project_root is None:
        return SourceResolution(False, reason="no project root")
    state_path = project_root / ".jiacong" / "source.json"
    if not state_path.is_file():
        return SourceResolution(False, reason="source.json missing")
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return SourceResolution(False, reason="source.json schema is not object")
        source_root_raw = str(data.get("source_root") or "").strip()
        main_name = str(data.get("main_name") or "main").strip()
        worktrees_root_raw = str(data.get("worktrees_root") or "").strip()
        source_dir = str(data.get("source_dir") or "").strip()
        if not source_root_raw or not main_name or not worktrees_root_raw or not source_dir:
            return SourceResolution(False, reason="source.json missing required layout fields")
        source_root = _safe_project_relative_path(project_root, source_root_raw)
        main_worktree = _safe_project_relative_path(project_root, f"{source_root_raw}/{main_name}")
        worktrees_root = _safe_project_relative_path(project_root, worktrees_root_raw)
        if source_root is None or main_worktree is None or worktrees_root is None:
            return SourceResolution(False, reason="source paths escape project root")
        if not source_root.exists() or not main_worktree.exists() or not worktrees_root.exists():
            return SourceResolution(False, reason="source layout paths missing")
        return SourceResolution(
            True,
            source_root=source_root,
            main_worktree=main_worktree,
            worktrees_root=worktrees_root,
            source_dir=source_dir,
            git_enabled=bool(data.get("git_enabled")),
            reason="source.json resolved",
        )
    except Exception as exc:
        return SourceResolution(False, reason=f"source.json unreadable: {type(exc).__name__}")


def _safe_project_relative_path(project_root: Path, raw: str) -> Path | None:
    try:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        resolved = candidate.expanduser().resolve()
        resolved.relative_to(project_root.resolve())
        return resolved
    except Exception:
        return None


def plugin_root(default_file: str | Path) -> Path:
    for env_name in ("JIACONG_FLOW_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        try:
            value = os.environ.get(env_name, "").strip()
            if value:
                return Path(value).expanduser().resolve()
        except Exception:
            pass
    return Path(default_file).resolve().parent.parent


def skill_dir(plugin_root_path: Path) -> Path:
    return plugin_root_path / "skills" / "smarter-project"


def script_path(plugin_root_path: Path, script_name: str) -> Path:
    return skill_dir(plugin_root_path) / "scripts" / script_name


def state_dir(project_root: Path) -> Path:
    path = project_root / ".jiacong"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def workspace_state_dir(workspace_root: Path) -> Path:
    path = workspace_root / WORKSPACE_STATE_DIR
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def is_managed_project_root(root: Path) -> bool:
    return audit_confirm_marker(root).valid


def git_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def known_project_roots(roots: RootResolution) -> list[Path]:
    found: list[Path] = []

    def add(path: Path | None) -> None:
        if path is None:
            return
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in found:
            return
        if is_managed_project_root(resolved):
            found.append(resolved)

    add(roots.project_root)
    add(roots.candidate_root)
    if roots.workspace_root is not None:
        workspace = roots.workspace_root
        add(workspace / "main")
        worktrees_dir = workspace / "worktrees"
        if worktrees_dir.is_dir():
            try:
                for child in worktrees_dir.iterdir():
                    if child.is_dir():
                        add(child)
            except Exception:
                pass

    if roots.scan is not None:
        for child in roots.scan.confirmed_children:
            add(child.path)
    return found


def project_context_message(roots: RootResolution, project_root: Path) -> str:
    branch = git_branch(project_root)
    source = resolve_source(project_root)
    try:
        root_label = str(project_root.resolve())
    except Exception:
        root_label = str(project_root)
    try:
        cwd_label = str(roots.cwd.resolve())
    except Exception:
        cwd_label = str(roots.cwd)
    return msg(
        "context.project_root",
        project_root=root_label,
        root_kind=roots.kind,
        branch=f" · branch={branch}" if branch else "",
        selection=f" · selection={roots.selection}" if roots.selection else "",
    )


def unmanaged_root_messages(roots: RootResolution, plugin_root_path: Path) -> list[str]:
    if roots.project_root is not None:
        return []
    values = _message_values(roots, plugin_root_path)
    return [msg(_root_message_key(roots), **values)]


def session_unmanaged_messages(roots: RootResolution, plugin_root_path: Path) -> list[str]:
    if roots.project_root is not None:
        return []
    values = _message_values(roots, plugin_root_path)
    return [msg(_session_message_key(roots), **values)]


def audit_confirm_marker(root: Path) -> MarkerAudit:
    marker = root / CONFIRM_MARKER
    try:
        if not marker.exists():
            return MarkerAudit("missing", marker)
        if not marker.is_file():
            return MarkerAudit("not_file", marker, reason="marker path is not a file")
        try:
            resolved_root = root.expanduser().resolve()
            resolved_marker = marker.resolve()
            resolved_marker.relative_to(resolved_root)
        except Exception:
            return MarkerAudit("path_mismatch", marker, reason="marker escapes project root")
        try:
            raw = marker.read_text(encoding="utf-8")
        except Exception as exc:
            return MarkerAudit("unreadable", marker, reason=type(exc).__name__)
        try:
            data = json.loads(raw)
        except Exception as exc:
            return MarkerAudit("invalid_json", marker, reason=type(exc).__name__)
        if not isinstance(data, dict):
            return MarkerAudit("invalid_schema", marker, reason="top-level JSON is not an object")
        if data.get("confirmed_root") is False:
            return MarkerAudit("unconfirmed_false", marker)
        declared_root = data.get("project_root") or data.get("root")
        if isinstance(declared_root, str) and declared_root.strip():
            declared_path = Path(declared_root).expanduser()
            if not declared_path.is_absolute():
                declared_path = root / declared_path
            try:
                if declared_path.resolve() != root.resolve():
                    return MarkerAudit("path_mismatch", marker, reason="declared project_root differs")
            except Exception:
                return MarkerAudit("path_mismatch", marker, reason="declared project_root cannot resolve")
        return MarkerAudit("valid_confirmed", marker, project_root=root)
    except Exception as exc:
        return MarkerAudit("unreadable", marker, reason=type(exc).__name__)


def _scan_layer(path: Path) -> LayerScan:
    errors: list[str] = []
    marker = audit_confirm_marker(path)
    legacy = _detected_project_traces(path, errors)
    jiacong, ecosystem = _split_trace_types(legacy)
    structure = _structure_features(path, errors)
    return LayerScan(
        path=path,
        marker=marker,
        legacy_traces=tuple(legacy),
        jiacong_legacy_traces=tuple(jiacong),
        agent_ecosystem_traces=tuple(ecosystem),
        structure=structure,
        is_home=_is_home(path),
        is_root=_is_root(path),
        is_shallow_mount=_is_shallow_mount(path),
        is_special_dir=_special_dir(path),
        scan_errors=tuple(errors),
    )


def _scan_children(current: Path, errors: list[str]) -> list[ChildScan]:
    children: list[ChildScan] = []
    if not current.is_dir():
        return children
    try:
        entries = sorted(current.iterdir(), key=lambda p: p.name.casefold())
    except Exception as exc:
        errors.append(f"{current}:iterdir:{type(exc).__name__}")
        return children
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except Exception as exc:
            errors.append(f"{entry}:is_dir:{type(exc).__name__}")
            continue
        child_errors: list[str] = []
        marker = audit_confirm_marker(entry)
        legacy = _detected_project_traces(entry, child_errors)
        structure = _structure_features(entry, child_errors)
        children.append(
            ChildScan(
                name=entry.name,
                path=entry,
                marker=marker,
                legacy_traces=tuple(legacy),
                structure=structure,
                scan_errors=tuple(child_errors),
            )
        )
    return children


def _detected_project_traces(root: Path, errors: list[str] | None = None) -> list[str]:
    found: list[str] = []
    for rel in LEGACY_TRACE_PATHS:
        path = root / rel
        try:
            if path.exists():
                found.append(rel + ("/" if path.is_dir() and not rel.endswith("/") else ""))
        except Exception as exc:
            if errors is not None:
                errors.append(f"{path}:exists:{type(exc).__name__}")
    return found


def _split_trace_types(traces: list[str]) -> tuple[list[str], list[str]]:
    jiacong: list[str] = []
    ecosystem: list[str] = []
    for trace in traces:
        normalized = trace.rstrip("/")
        if normalized in {"topics", "logs"}:
            jiacong.append(trace)
        else:
            ecosystem.append(trace)
    return jiacong, ecosystem


def _structure_features(root: Path, errors: list[str] | None = None) -> StructureFeatures:
    def exists(rel: str) -> bool:
        path = root / rel
        try:
            return path.exists()
        except Exception as exc:
            if errors is not None:
                errors.append(f"{path}:exists:{type(exc).__name__}")
            return False

    configs = tuple(name for name in PROJECT_CONFIG_FILES if exists(name))
    readme = any(exists(name) for name in README_FILES)
    sources = tuple(name + "/" for name in SOURCE_DIRS if exists(name))
    return StructureFeatures(
        has_git=exists(".git"),
        has_repo_git=exists(".repo.git"),
        has_main=exists("main"),
        has_worktrees=exists("worktrees"),
        project_configs=configs,
        has_readme=readme,
        source_dirs=sources,
    )


def _hard_risk_kind(layer: LayerScan) -> str | None:
    if layer.is_home:
        return "unsafe_home"
    if layer.is_root:
        return "unsafe_root"
    if layer.is_shallow_mount:
        return "unsafe_mount"
    return None


def _session_message_key(roots: RootResolution) -> str:
    if roots.kind == "unsafe_home":
        return "session.unsafe.home"
    if roots.kind == "unsafe_root":
        return "session.unsafe.root"
    if roots.kind == "unsafe_mount":
        return "session.unsafe.mount"
    return "session.needs_judgment"


def _root_message_key(roots: RootResolution) -> str:
    if roots.kind == "unsafe_home":
        return "root.unsafe.home"
    if roots.kind == "unsafe_root":
        return "root.unsafe.root"
    if roots.kind == "unsafe_mount":
        return "root.unsafe.mount"
    return "root.needs_judgment"


def _runtime_message_values() -> dict[str, object]:
    # 项目名不在 hook 提示里实例化：未绑定项目根时无项目名可填，
    # 系统署名 Jiacong Flow 直接写死在模板中。此处不再回填任何实例名。
    return {}


def runtime_message_values() -> dict[str, object]:
    return _runtime_message_values()


def _message_values(roots: RootResolution, plugin_root_path: Path) -> dict[str, object]:
    scan = roots.scan or scan_three_layers(roots.cwd)
    current = scan.current
    parent = scan.parent_layer
    confirmed_children = scan.confirmed_children
    values = _runtime_message_values()
    values.update({
        "cwd": scan.cwd,
        "parent": scan.parent,
        "dirname": scan.dirname,
        "cwd_source": scan.cwd_source,
        "cwd_confidence": scan.cwd_confidence,
        "marker": CONFIRM_MARKER,
        "marker_status": current.marker.status,
        "marker_status_display": _marker_status_display(current.marker),
        "has_confirmed_marker_display": _marker_display(current.marker),
        "parent_has_confirmed_marker_display": _marker_display(parent.marker),
        "legacy_traces_display": _list_display(current.legacy_traces),
        "parent_legacy_traces_display": _list_display(parent.legacy_traces),
        "structure_features_display": _structure_display(current.structure),
        "parent_structure_features_display": _structure_display(parent.structure),
        "special_dir_display": current.is_special_dir or "无",
        "children_summary": _children_summary(scan.children),
        "has_confirmed_subdirs_note": _confirmed_children_note(confirmed_children),
        "legacy_traces_explanation": _legacy_explanation(current),
        "migration_option": _migration_option(current),
        "init_script": script_path(plugin_root_path, "init_project.py"),
    })
    return values


def _marker_display(marker: MarkerAudit) -> str:
    if marker.valid:
        return f"有（{marker.path}）"
    return "无"


def _marker_status_display(marker: MarkerAudit) -> str:
    mapping = {
        "valid_confirmed": "有效",
        "missing": "无",
        "invalid_json": "无效（JSON 解析失败）",
        "invalid_schema": "无效（结构不符合要求）",
        "unconfirmed_false": "明确标记为未确认",
        "path_mismatch": "路径不匹配",
        "unreadable": "不可读",
        "not_file": "无效（不是文件）",
    }
    label = mapping.get(marker.status, marker.status)
    return f"{label}：{marker.reason}" if marker.reason else label


def _list_display(items: tuple[str, ...] | list[str]) -> str:
    return "有（" + "、".join(items) + "）" if items else "无"


def _structure_display(structure: StructureFeatures) -> str:
    features: list[str] = []
    if structure.has_git:
        features.append("Git 仓库")
    if structure.has_repo_git:
        features.append(".repo.git")
    if structure.has_main:
        features.append("main/ 子目录")
    if structure.has_worktrees:
        features.append("worktrees/ 子目录")
    if structure.project_configs:
        features.append("项目配置（" + "、".join(structure.project_configs) + "）")
    if structure.has_readme:
        features.append("README")
    if structure.source_dirs:
        features.append("源码目录（" + "、".join(structure.source_dirs) + "）")
    return "有（" + "、".join(features) + "）" if features else "无"


def _children_summary(children: tuple[ChildScan, ...]) -> str:
    if not children:
        return "无子目录或无法读取子目录"
    confirmed = [child.name for child in children if child.marker.valid]
    git_dirs = [child.name for child in children if child.structure.has_git]
    legacy_dirs = [child.name for child in children if child.legacy_traces]
    highlights: list[str] = []
    for names in (confirmed, git_dirs, legacy_dirs):
        for name in names:
            if name not in highlights:
                highlights.append(name)
    parts = [f"共 {len(children)} 个子目录"]
    if confirmed:
        parts.append(f"{len(confirmed)} 个含确认标记")
    if git_dirs:
        parts.append(f"{len(git_dirs)} 个含 Git")
    if legacy_dirs:
        parts.append(f"{len(legacy_dirs)} 个含旧痕迹")
    if highlights:
        parts.append("重点目录：" + "、".join(highlights[:12]) + (" 等" if len(highlights) > 12 else ""))
    return "；".join(parts)


def _confirmed_children_note(children: tuple[ChildScan, ...]) -> str:
    if not children:
        return ""
    paths = "、".join(str(child.path) for child in children[:8])
    suffix = " 等" if len(children) > 8 else ""
    return f"检测到下一层有已确认项目根（{paths}{suffix}），可以建议用户切换到该目录，但不能自动切换或自动启用项目治理。"


def _legacy_explanation(layer: LayerScan) -> str:
    if not layer.legacy_traces:
        return ""
    return (
        "\n       - 检测到 AI 协作或旧项目管理痕迹（"
        + "、".join(layer.legacy_traces)
        + "）\n       - 这些痕迹可能来自旧版本插件，也可能来自其他 Agent\n"
        + "       - 这些痕迹只能作为线索，不能作为项目根授权依据"
    )


def _migration_option(layer: LayerScan) -> str:
    if not layer.legacy_traces:
        return ""
    return (
        "\n       方案 C：迁移旧痕迹到具体项目目录\n"
        "       - 将旧痕迹（" + "、".join(layer.legacy_traces) + "）移动到具体项目目录\n"
        "       - 在目标目录创建 .jiacong/project.json 确认\n"
        "       - 适合：保留旧项目管理历史\n"
        "       - 操作：用户确认后，移动文件并在目标目录建档"
    )


def _resolve_current(cwd: str | Path | None) -> Path:
    if cwd is not None:
        try:
            return Path(cwd).expanduser().resolve()
        except Exception:
            return Path(cwd)
    # kwargs 未传 cwd 时，从环境变量获取（Hermes WebUI/CLI 设置 TERMINAL_CWD，
    # CLI 和 cron 也可能设置 HERMES_CWD）。这是 gateway daemon 进程中
    # Path.cwd() 不等于用户项目目录时的关键 fallback。
    for env_key in ("HERMES_CWD", "TERMINAL_CWD"):
        value = os.environ.get(env_key, "").strip()
        if value:
            try:
                p = Path(value).expanduser().resolve()
                if p.is_dir():
                    return p
            except Exception:
                pass
    return Path.cwd().resolve()


def _cwd_source() -> str:
    # 与 _resolve_current 一致：HERMES_CWD 优先，TERMINAL_CWD 次之。
    # 但本函数只用于诊断显示，不影响路径解析逻辑。
    if os.environ.get("HERMES_CWD", "").strip():
        return "HERMES_CWD"
    if os.environ.get("TERMINAL_CWD", "").strip():
        return "TERMINAL_CWD"
    if os.environ.get("JIACONG_FLOW_CWD", "").strip():
        return "JIACONG_FLOW_CWD"
    return "process_cwd"


def _cwd_confidence(source: str) -> str:
    # 环境变量来源置信度为 medium（不是 kwargs 显式传递的高），
    # process_cwd 最低（daemon 进程的 cwd 可能不是项目目录）。
    return {"HERMES_CWD": "medium", "TERMINAL_CWD": "medium", "JIACONG_FLOW_CWD": "medium", "process_cwd": "low"}.get(source, "low")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _is_home(path: Path) -> bool:
    try:
        return path.expanduser().resolve() == Path.home().resolve()
    except Exception:
        return False


def _is_root(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
        return resolved.parent == resolved
    except Exception:
        return False


def _is_shallow_mount(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
        parts = resolved.parts
        return len(parts) <= 3 and parts[:2] == ("/", "mnt")
    except Exception:
        return False


def _special_dir(path: Path) -> str | None:
    try:
        resolved = path.expanduser().resolve()
        name = resolved.name.casefold()
        home = Path.home().resolve()
        if resolved.parent == home:
            if name in {"desktop", "桌面"}:
                return "desktop"
            if name in {"downloads", "下载"}:
                return "downloads"
            if name in {"documents", "文档"}:
                return "documents"
        parts = tuple(part.casefold() for part in resolved.parts)
        if len(parts) >= 5 and parts[1] == "mnt" and "users" in parts:
            if name == "desktop":
                return "desktop"
            if name == "downloads":
                return "downloads"
            if name == "documents":
                return "documents"
    except Exception:
        return None
    return None
