# -*- coding: utf-8 -*-
"""Manage the active worktree for a jiacong-flow workspace container.

This script is the automation layer behind `.jiacong-workspace/current-worktree`.
It does not switch Git branches inside a worktree. It selects which existing
worktree the outer workspace container should route Codex hooks to.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


STATE_DIR = ".jiacong-workspace"
CURRENT_FILE = "current-worktree"
CURRENT_META_FILE = "current-worktree.json"
ARCHIVE_DIR = "archive"
ARCHIVE_BRANCH_DIR = "branches"


@dataclass(frozen=True)
class Worktree:
    path: Path
    rel: str
    branch: str
    head: str = ""
    bare: bool = False
    detached: bool = False

    @property
    def label(self) -> str:
        if self.branch:
            return self.branch
        return self.rel


@dataclass(frozen=True)
class ArchivePlan:
    worktree: Worktree
    timestamp: str
    archive_dir: Path
    snapshot_dir: Path
    metadata_path: Path
    tag: str
    delete_branch: bool
    head: str


def _configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def _as_posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def find_workspace(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).expanduser().resolve()
    for candidate in (current, *current.parents):
        if _is_workspace(candidate):
            return candidate
    raise SystemExit(
        "[error] 未找到 jiacong-flow workspace 容器：需要 .repo.git 且包含 main/ 或 worktrees/"
    )


def _is_workspace(path: Path) -> bool:
    return (path / ".repo.git").exists() and (
        (path / "main").is_dir() or (path / "worktrees").is_dir()
    )


def _rel_to_workspace(path: Path, workspace: Path) -> str:
    try:
        return _as_posix(path.resolve().relative_to(workspace.resolve()))
    except Exception:
        return _as_posix(path.resolve())


def _run_git_worktree_list(workspace: Path) -> str:
    result = subprocess.run(
        ["git", "--git-dir", str(workspace / ".repo.git"), "worktree", "list", "--porcelain"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git worktree list failed")
    return result.stdout


def parse_worktree_porcelain(text: str, workspace: Path) -> list[Worktree]:
    entries: list[dict[str, object]] = []
    current: dict[str, object] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            if current:
                entries.append(current)
            current = {"path": Path(line[len("worktree ") :])}
        elif line == "bare":
            current["bare"] = True
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            branch = line[len("branch ") :]
            if branch.startswith("refs/heads/"):
                branch = branch[len("refs/heads/") :]
            current["branch"] = branch
        elif line == "detached":
            current["detached"] = True
    if current:
        entries.append(current)

    worktrees: list[Worktree] = []
    for entry in entries:
        path = Path(entry.get("path", "")).expanduser().resolve()
        bare = bool(entry.get("bare", False))
        if bare:
            continue
        worktrees.append(
            Worktree(
                path=path,
                rel=_rel_to_workspace(path, workspace),
                branch=str(entry.get("branch", "")),
                head=str(entry.get("head", "")),
                bare=bare,
                detached=bool(entry.get("detached", False)),
            )
        )
    return sorted(worktrees, key=lambda item: (item.rel != "main", item.rel))


def _fallback_scan(workspace: Path) -> list[Worktree]:
    candidates: list[Path] = []
    if (workspace / "main" / ".git").exists():
        candidates.append(workspace / "main")
    worktrees_dir = workspace / "worktrees"
    if worktrees_dir.is_dir():
        for path in worktrees_dir.rglob(".git"):
            candidates.append(path.parent)

    result: list[Worktree] = []
    for path in candidates:
        rel = _rel_to_workspace(path, workspace)
        result.append(Worktree(path=path.resolve(), rel=rel, branch=_git_branch(path)))
    return sorted(result, key=lambda item: (item.rel != "main", item.rel))


def _git_branch(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "branch", "--show-current"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _git_head(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git rev-parse failed")
    return result.stdout.strip()


def _git_status(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git status failed")
    return result.stdout


def _run_git_repo(workspace: Path, args: list[str]) -> None:
    result = subprocess.run(
        ["git", "--git-dir", str(workspace / ".repo.git"), *args],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")


def list_worktrees(workspace: Path) -> list[Worktree]:
    try:
        parsed = parse_worktree_porcelain(_run_git_worktree_list(workspace), workspace)
        if parsed:
            return parsed
    except Exception:
        pass
    return _fallback_scan(workspace)


def read_current(workspace: Path) -> str:
    path = workspace / STATE_DIR / CURRENT_FILE
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                return value
    except Exception:
        pass
    return ""


def resolve_target(target: str, worktrees: list[Worktree], workspace: Path) -> Worktree:
    raw = target.strip().strip('"').strip("'")
    if not raw:
        raise SystemExit("[error] target 不能为空")

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = workspace / raw
    try:
        candidate = candidate.expanduser().resolve()
    except Exception:
        candidate = Path(raw)

    matches = [
        item
        for item in worktrees
        if raw in {item.rel, item.branch, item.path.name}
        or candidate == item.path
        or _as_posix(raw) == _as_posix(item.path)
    ]

    if not matches:
        available = ", ".join(item.rel for item in worktrees) or "(none)"
        raise SystemExit(f"[error] 未找到 worktree: {target}\n[hint] 可用：{available}")
    if len(matches) > 1:
        available = ", ".join(f"{item.rel} ({item.branch})" for item in matches)
        raise SystemExit(f"[error] target 有歧义：{target}\n[hint] 匹配：{available}")
    return matches[0]


def write_current(workspace: Path, worktree: Worktree) -> None:
    state_dir = workspace / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / CURRENT_FILE).write_text(worktree.rel + "\n", encoding="utf-8")
    payload = {
        "active": worktree.rel,
        "branch": worktree.branch,
        "path": str(worktree.path),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "managed": _is_managed_project(worktree.path),
    }
    (state_dir / CURRENT_META_FILE).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _is_managed_project(path: Path) -> bool:
    return (path / ".claude" / "CLAUDE.md").is_file() or (
        (path / ".claude").is_dir() and (path / "topics").is_dir()
    )


def _status_payload(workspace: Path, worktrees: list[Worktree]) -> dict:
    current = read_current(workspace)
    active = None
    if current:
        try:
            active = resolve_target(current, worktrees, workspace)
        except SystemExit:
            active = None
    return {
        "workspace": str(workspace),
        "current": current,
        "active": {
            "rel": active.rel,
            "branch": active.branch,
            "path": str(active.path),
            "managed": _is_managed_project(active.path),
        }
        if active
        else None,
        "worktrees": [
            {
                "rel": item.rel,
                "branch": item.branch,
                "path": str(item.path),
                "managed": _is_managed_project(item.path),
            }
            for item in worktrees
        ],
    }


def _safe_archive_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    safe = safe.strip(".-")
    return safe or "detached"


def _archive_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _is_active_worktree(
    current: str,
    worktree: Worktree,
    worktrees: list[Worktree],
    workspace: Path,
) -> bool:
    if not current:
        return False
    try:
        return resolve_target(current, worktrees, workspace).path == worktree.path
    except SystemExit:
        return current in {worktree.rel, worktree.branch, worktree.path.name}


def _assert_archivable(
    workspace: Path,
    worktree: Worktree,
    worktrees: list[Worktree],
    *,
    delete_branch: bool,
) -> None:
    if worktree.rel == "main":
        raise SystemExit("[error] main worktree cannot be archived; main is the workspace baseline")
    if not worktree.branch:
        raise SystemExit("[error] detached worktree has no branch name and cannot be branch-archived")
    if delete_branch and worktree.branch == "main":
        raise SystemExit("[error] main branch cannot be deleted")
    current = read_current(workspace)
    if _is_active_worktree(current, worktree, worktrees, workspace):
        raise SystemExit(
            "[error] cannot archive the active worktree; run `use main` or select another worktree first"
        )
    dirty = _git_status(worktree.path).strip()
    if dirty:
        preview = "\n".join(dirty.splitlines()[:20])
        raise SystemExit(f"[error] worktree is dirty; commit or stash before archiving:\n{preview}")


def build_archive_plan(
    workspace: Path,
    worktree: Worktree,
    *,
    delete_branch: bool = True,
    timestamp: str | None = None,
) -> ArchivePlan:
    stamp = timestamp or _archive_timestamp()
    branch_or_rel = worktree.branch or worktree.rel
    archive_root = (
        workspace
        / STATE_DIR
        / ARCHIVE_DIR
        / ARCHIVE_BRANCH_DIR
        / _safe_archive_name(branch_or_rel)
        / stamp
    )
    head = worktree.head or _git_head(worktree.path)
    return ArchivePlan(
        worktree=worktree,
        timestamp=stamp,
        archive_dir=archive_root,
        snapshot_dir=archive_root / "snapshot",
        metadata_path=archive_root / "metadata.json",
        tag=f"archive/{worktree.branch}/{stamp}",
        delete_branch=delete_branch,
        head=head,
    )


def _copy_archive_snapshot(plan: ArchivePlan) -> None:
    if plan.archive_dir.exists():
        raise SystemExit(f"[error] archive directory already exists: {plan.archive_dir}")
    plan.archive_dir.mkdir(parents=True, exist_ok=False)
    shutil.copytree(
        plan.worktree.path,
        plan.snapshot_dir,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ),
    )


def _restore_commands(plan: ArchivePlan) -> list[str]:
    rel = plan.worktree.rel
    branch = plan.worktree.branch
    if plan.delete_branch:
        return [
            f"git --git-dir .repo.git worktree add -b {branch} {rel} {plan.tag}",
            f"python app/workspace_use.py --workspace . use {branch}",
        ]
    return [
        f"git --git-dir .repo.git worktree add {rel} {branch}",
        f"python app/workspace_use.py --workspace . use {branch}",
    ]


def _write_archive_metadata(workspace: Path, plan: ArchivePlan) -> None:
    payload = {
        "archived_at": plan.timestamp,
        "workspace": str(workspace),
        "source": {
            "rel": plan.worktree.rel,
            "branch": plan.worktree.branch,
            "path": str(plan.worktree.path),
            "head": plan.head,
        },
        "archive": {
            "path": str(plan.archive_dir),
            "snapshot": str(plan.snapshot_dir),
            "metadata": str(plan.metadata_path),
        },
        "git": {
            "tag": plan.tag,
            "branch_deleted": plan.delete_branch,
        },
        "restore": _restore_commands(plan),
    }
    plan.metadata_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def archive_worktree(
    workspace: Path,
    worktree: Worktree,
    worktrees: list[Worktree],
    *,
    dry_run: bool = False,
    keep_branch: bool = False,
    timestamp: str | None = None,
) -> ArchivePlan:
    delete_branch = not keep_branch
    _assert_archivable(workspace, worktree, worktrees, delete_branch=delete_branch)
    plan = build_archive_plan(
        workspace,
        worktree,
        delete_branch=delete_branch,
        timestamp=timestamp,
    )
    if plan.archive_dir.exists():
        raise SystemExit(f"[error] archive directory already exists: {plan.archive_dir}")
    if dry_run:
        return plan

    _copy_archive_snapshot(plan)
    _run_git_repo(workspace, ["tag", plan.tag, plan.head])
    _run_git_repo(workspace, ["worktree", "remove", str(worktree.path)])
    if delete_branch:
        _run_git_repo(workspace, ["branch", "-D", worktree.branch])
    _write_archive_metadata(workspace, plan)
    return plan


def print_status(workspace: Path, worktrees: list[Worktree], as_json: bool = False) -> None:
    payload = _status_payload(workspace, worktrees)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"[workspace] {payload['workspace']}")
    print(f"[active] {payload['current'] or '(未选择)'}")
    for item in payload["worktrees"]:
        marker = "*" if item["rel"] == payload["current"] else " "
        managed = "managed" if item["managed"] else "candidate"
        branch = item["branch"] or "(detached)"
        print(f"{marker} {item['rel']}  branch={branch}  {managed}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="jiacong-flow workspace active worktree manager")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="workspace 容器根；默认从 cwd 向上查找",
    )
    parser.add_argument("--json", action="store_true", help="status/list 使用 JSON 输出")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="列出 workspace worktrees")
    sub.add_parser("status", help="显示当前 active worktree")
    use = sub.add_parser("use", help="选择 active worktree")
    use.add_argument("target", help="worktree 相对路径、branch 名或绝对路径")
    archive = sub.add_parser("archive", help="归档非 active worktree：快照 + tag + 移除 worktree")
    archive.add_argument("target", help="worktree 相对路径、branch 名或绝对路径")
    archive.add_argument("--dry-run", action="store_true", help="只显示归档计划，不写入")
    archive.add_argument(
        "--keep-branch",
        action="store_true",
        help="保留本地 branch；默认删除 branch 以从分支列表中隐藏",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    args = parse_args(argv)
    workspace = find_workspace(args.workspace)
    worktrees = list_worktrees(workspace)

    if args.command == "list":
        if args.json:
            print(json.dumps(_status_payload(workspace, worktrees)["worktrees"], ensure_ascii=False, indent=2))
        else:
            for item in worktrees:
                print(f"{item.rel}\t{item.branch or '(detached)'}\t{item.path}")
        return 0

    if args.command == "status":
        print_status(workspace, worktrees, as_json=args.json)
        return 0

    if args.command == "use":
        selected = resolve_target(args.target, worktrees, workspace)
        write_current(workspace, selected)
        managed = "managed" if _is_managed_project(selected.path) else "candidate"
        print(f"[ok] active worktree = {selected.rel}  branch={selected.branch or '(detached)'}  {managed}")
        return 0

    if args.command == "archive":
        selected = resolve_target(args.target, worktrees, workspace)
        plan = archive_worktree(
            workspace,
            selected,
            worktrees,
            dry_run=args.dry_run,
            keep_branch=args.keep_branch,
        )
        prefix = "[dry-run]" if args.dry_run else "[ok]"
        print(f"{prefix} archive target = {selected.rel}  branch={selected.branch}")
        print(f"{prefix} snapshot = {plan.snapshot_dir}")
        print(f"{prefix} tag = {plan.tag}")
        if plan.delete_branch:
            print(f"{prefix} branch hidden = yes")
        else:
            print(f"{prefix} branch hidden = no (--keep-branch)")
        print(f"{prefix} metadata = {plan.metadata_path}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
