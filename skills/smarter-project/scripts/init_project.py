# -*- coding: utf-8 -*-
"""
init_project.py · 按套餐初始化项目脚手架

用法：
    python init_project.py <项目根> --type <学术/实证/代码/短平快>

说明：
    - 按 references/init-project.md 四套架构套餐创建目录树
    - 写入 logs/stream.md、.gitignore 等基础文件
    - 写入 topics/_seeds.md 提示文件（套餐推荐的 root 标签清单 + 示范命令）
    - **不再建根话题目录**（C 方案）：topics/ 保持"纯讨论晶格"，成型内容走 doc/
    - 幂等：已存在的目录/文件不覆盖，给出跳过提示
    - 检测旧目录结构：发现 topics/NNN_套餐根/ 形式的旧根话题目录时，
      输出建议报告供 AI 与用户讨论迁移策略（不自动改动）

命名说明：文件名用下划线 (init_project.py)，对称 skill-creator 官方 init_skill.py 避免混淆。
"""
from __future__ import annotations

import argparse
import re
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import (  # noqa: E402
    configure_stdout_utf8,
    ensure_project_root,
    now_date,
    now_datetime,
)
from _lib.store import (  # noqa: E402
    find_templates_dir,
    framework_doc_path,
    framework_readme_path,
    load_architecture,
    render_framework_file_context,
    render_template as _render,
)
from _lib.entrypoints import write_project_entrypoints  # noqa: E402


def _write_if_absent(path: Path, content: str, report: list) -> None:
    """只在文件不存在时写入，幂等。"""
    if path.exists():
        report.append(f"  [skip] {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    report.append(f"  [write] {path}")


def _project_entry_guard() -> str:
    return """Root decision guard:

- This directory is the managed project root because it has a valid `.jiacong/project.json`. Keep `topics/`, `logs/`, `doc/`, and `.claude/` here.
- If this directory is also a normal `.git` repository, prefer in-place branch work from this root.
- Do not create another outer workspace around an existing managed root unless a migration plan is explicit.
- If opened from a workspace container, resolve `.jiacong-workspace/current-worktree` first, then enter this root.
- If `.git` and `.repo.git` are mixed, multiple child repos exist, or only partial `.claude/topics/logs` traces exist, stop automatic init and ask for a migration decision.
"""


def _workspace_entry_guard(main_name: str) -> str:
    return f"""Root decision guard:

- This outer directory is only a workspace container. Do not write `topics/` or `logs/` here.
- Active project roots are `{main_name}/` and `worktrees/<branch>/`.
- Resolve `.jiacong-workspace/current-worktree` before reading or writing project state.
- A normal `.git` repository should usually be initialized in place, not adopted into this container automatically.
- `--adopt-existing` is only for ordinary history folders with no `.git` and no `.claude/topics/logs`.
- Mixed `.git` + `.repo.git`, multiple child repos, or partial smarter-project traces require an explicit migration decision before init.
"""


def _write_project_confirmation(root: Path, project_type: str, report: list[str]) -> None:
    """写入项目根确认标记；这是新版根安全门控的唯一授权依据。"""
    marker = root / ".jiacong" / "project.json"
    if marker.exists():
        report.append(f"  [skip] {marker}")
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": root.name,
        "project_type": project_type,
        "confirmed_root": True,
        "project_root": str(root.resolve()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "schema_version": 1,
    }
    marker.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report.append(f"  [write] {marker}")


def _framework_entry_summary(base_topic: dict) -> str:
    """为项目入口渲染 Framework 指针摘要。"""
    toc = base_topic.get("toc") or []
    parts = []
    for item in toc:
        title = str(item.get("title") or item.get("name") or "").strip() if isinstance(item, dict) else str(item).strip()
        if title:
            parts.append(title)
    if not parts:
        return "记录本层稳定结论和跨话题复用规则"
    return "、".join(parts[:5])


def _framework_entries(base_topics: list[dict]) -> list[dict[str, str]]:
    """把套餐 base_topics 转成 AGENTS.md 的 Framework 指针表。"""
    entries = []
    for bt in base_topics:
        name = str(bt.get("name") or "").strip()
        if not name:
            continue
        entries.append({
            "name": name,
            "doc_path": framework_doc_path(name),
            "summary": _framework_entry_summary(bt),
        })
    return entries


def _write_project_cli_entries(project_root: Path, project_type: str, report: list) -> None:
    """写入多 CLI 项目级入口；`AGENTS.md` 是 canonical 主入口。"""
    templates_dir = find_templates_dir(__file__)
    pkg = load_architecture(project_type, templates_dir)
    tmpl_path = templates_dir / "project" / "project_entry.md.tmpl"
    dirs = set(pkg.get("dirs", []))
    agents_entry = None
    if tmpl_path.exists():
        agents_entry = _render(
            tmpl_path.read_text(encoding="utf-8"),
            {
                "project_name": project_root.name,
                "project_type": project_type,
                "today": now_date(),
                "roots": [{"label": label} for _, label in pkg.get("roots", [])],
                "framework_entries": _framework_entries(pkg.get("base_topics", [])),
                "has_topics": "topics" in dirs,
                "has_base": "base" in dirs,
            },
        )
    payload = write_project_entrypoints(project_root, project_type=project_type, agents_entry=agents_entry)
    for rel_path in [payload["canonical"], *payload["adapters"].values(), ".jiacong/entrypoints.json"]:
        report.append(f"  [write] {project_root / rel_path}")


def _write_workspace_cli_entries(workspace_root: Path, main_name: str, report: list) -> None:
    """写入 workspace 容器级 CLI 入口；该层不承载 topics/logs。"""
    guard = _workspace_entry_guard(main_name)
    agents = f"""# {workspace_root.name} workspace container

This directory is a workspace container, not a normal single-branch project root.

Active project roots live under:

- `{main_name}/` for the main worktree.
- `worktrees/<branch>/` for feature, refactor, and agent worktrees.

Workspace state:

- Git metadata: `.repo.git`
- Active project selection: `.jiacong-workspace/current-worktree`
- Active project metadata: `.jiacong-workspace/current-worktree.json`

When working from this outer folder, first resolve the active project root from
`.jiacong-workspace/current-worktree`, then follow that inner worktree's
`AGENTS.md` and the adapter file for the current CLI.
{guard}
"""
    claude = f"""# {workspace_root.name} workspace container

This is a workspace container. It does not own `topics/` or `logs/`.

Use `.jiacong-workspace/current-worktree` to choose the active project root:

- `{main_name}/`
- `worktrees/<branch>/`

After resolving the active project root, follow its root `AGENTS.md`; this
`CLAUDE.md` is only the container-level adapter.
{guard}
"""
    gemini = f"""# {workspace_root.name} workspace container

This is a workspace container, not the managed project root.

Read `.jiacong-workspace/current-worktree` to find the active project root, then
follow that project root's `AGENTS.md` and `GEMINI.md` adapter.
{guard}
"""
    _write_if_absent(workspace_root / "AGENTS.md", agents, report)
    _write_if_absent(workspace_root / "CLAUDE.md", claude, report)
    _write_if_absent(workspace_root / "GEMINI.md", gemini, report)


def _has_project_root_payload(root: Path) -> bool:
    """检测 root 是否已经像一个项目根，避免外层/内层双重建档。"""
    markers = [
        root / ".claude",
        root / "topics",
        root / "logs",
    ]
    return any(marker.exists() for marker in markers)


def _collect_adoptable_payload(workspace_root: Path, main_name: str) -> list[Path]:
    """收集可迁入 main/ 的历史文件；只处理未建档、无 git 的普通目录。"""
    reserved = {
        ".repo.git",
        ".jiacong-workspace",
        "worktrees",
        main_name,
    }
    payload: list[Path] = []
    for child in workspace_root.iterdir():
        if child.name == ".git":
            raise SystemExit(
                "[错误] 当前目录已有 .git。--adopt-existing 只支持无 git 的历史文件目录；"
                "请先手动确认迁移策略，避免破坏既有仓库。"
            )
        if child.name in reserved:
            continue
        payload.append(child)
    return payload


def _adopt_existing_payload(payload: list[Path], main_root: Path, report: list[str]) -> None:
    """把历史文件移动进 main/。先检查冲突，避免半迁移。"""
    if not payload:
        report.append("  [adopt] 无历史文件需要迁入 main/")
        return

    conflicts = [path.name for path in payload if (main_root / path.name).exists()]
    if conflicts:
        raise SystemExit(
            "[错误] main/ 内已存在同名文件，停止迁移以避免覆盖："
            + ", ".join(sorted(conflicts))
        )

    main_root.mkdir(parents=True, exist_ok=True)
    for path in payload:
        target = main_root / path.name
        shutil.move(str(path), str(target))
        report.append(f"  [adopt] {path.name} -> {target.relative_to(main_root.parent)}")


def _write_seeds_hint(project_root: Path, roots: list, pkg_name: str, report: list) -> None:
    """
    写 topics/_seeds.md：**提示文件，不是话题卡**。
    列出本套餐推荐的 root 标签清单 + 示范 topic_new 命令。
    AI 或用户建话题时参考此文件选 --root 标签。
    """
    seeds_path = project_root / "topics" / "_seeds.md"
    if seeds_path.exists():
        report.append(f"  [skip] {seeds_path}")
        return
    if not roots:
        # 短平快套餐无 roots，不写 _seeds.md
        return

    lines = [
        f"# 推荐根标签（{pkg_name}套餐）",
        "",
        "> 本文件是**提示文件**，不是话题卡。`topics/` 下只放子话题目录（讨论晶格），",
        "> 成型内容走 `doc/`；项目级最高压缩层走 `doc/Framework/`（见 SKILL.md §2.1 话题）。",
        "",
        f"本套餐的推荐 root 分组标签（`tree_gen.py` 按此字段分组渲染）：",
        "",
    ]
    for _slug, root_label in roots:
        lines.append(f"- `{root_label}`")
    lines.extend([
        "",
        "## 话题触发提示",
        "",
        "本文件只提示 root 标签，不自动创建话题。若讨论开始围绕项目目标如何写成可维护文档、CLAUDE.md / card / doc 如何分工、讨论材料如何迁入 doc 等问题打转，先按 `topic-lifecycle.md` 判断是否需要新建或切换到一个文档生成相关话题。若讨论改变项目目标、结构、风格或任务链，先在当前话题记录过程，再回查 `doc/Framework/` 对应主文件是否需要维护。",
        "",
        "这个话题不预设固定 TOC；它应先承载厚说明：本项目的目标、讨论、沉淀与交付文本如何互相生成。简称、parent 与 root 仍需按正常话题流程与用户对齐。",
        "",
        "## 新建话题示范",
        "",
        "```bash",
        "python <skill>/scripts/topic_new.py <项目根> <简称> \\",
        "    --parent null \\",
        f"    --root {roots[0][1] if roots else '🎯目标'} \\",
        '    --note "初始备注"',
        "```",
        "",
        "## 说明",
        "",
        "- `--parent null` = 顶层话题（无父）",
        "- `--root <标签>` = 分组标签（从上面清单选一个，也可自定义）",
        "- 同一 root 下可有多个兄弟话题",
        "- 标签不是强制契约（SKILL.md 硬纪律 §6），按项目需要可新增",
        "",
    ])
    _write_if_absent(seeds_path, "\n".join(lines), report)


def _detect_legacy(project_root: Path, roots: list) -> list[str]:
    """
    检测旧版根话题目录。
    旧版 init_project 会建 topics/001_目标/card.md + scratch.md 形式的根话题，
    C 方案不再建；若检测到，输出建议报告（不自动改动）。
    """
    warnings: list[str] = []
    topics_dir = project_root / "topics"
    if not topics_dir.exists():
        return warnings

    legacy_slugs = {slug for slug, _ in roots}
    found: list[Path] = []
    for child in topics_dir.iterdir():
        if not child.is_dir():
            continue
        if child.name in legacy_slugs:
            # 旧根话题目录（001_目标 等）
            if (child / "card.md").exists() or (child / "scratch.md").exists():
                found.append(child)

    if found:
        warnings.append("")
        warnings.append("⚠️ **检测到旧版根话题目录**（C 方案前的残留）：")
        for p in found:
            warnings.append(f"   - {p.relative_to(project_root)}")
        warnings.append("")
        warnings.append("建议处理（请用户决策）：")
        warnings.append("  (a) 若内容已沉淀为正式文档 → 迁 `doc/` 后手工删除话题目录")
        warnings.append("  (b) 若仍在讨论 → 保留但改名为子话题（如 010_目标讨论）")
        warnings.append("  (c) 若积重难返 → 整体移入 `reference/` 作为上轮参考")
        warnings.append("  (d) 若仍想保留根话题形态 → 跳过本提示，不影响 tree_gen 按 root 字段分组")
        warnings.append("")
        warnings.append("脚本不自动改动。AI 应与用户讨论后执行迁移。")
    return warnings


SOURCE_PAYLOAD_DIRS = {"src", "app", "lib", "pkg", "packages", "apps"}


def init_project_root(root: Path, project_type: str, *, skip_source_dirs: bool = False) -> tuple[list[str], list[str]]:
    """初始化一个真实项目根；返回 (report, legacy_warnings)。"""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    root = ensure_project_root(root)
    templates_dir = find_templates_dir(__file__)
    pkg = load_architecture(project_type, templates_dir)

    report: list[str] = [f"[init] 项目根：{root}", f"[init] 套餐：{project_type}"]

    # 0) 写项目根确认标记。确认标记是根安全门控的唯一授权依据。
    _write_project_confirmation(root, project_type, report)

    # 1) 旧目录检测（仅告警，不改动）
    legacy = _detect_legacy(root, pkg.get("roots", []))

    # 2) 建目录（全）
    for d in pkg["dirs"]:
        if skip_source_dirs and d.strip("/") in SOURCE_PAYLOAD_DIRS:
            report.append(f"  [skip] {d}（源码层 workspace 承载）")
            continue
        (root / d).mkdir(parents=True, exist_ok=True)
        report.append(f"  [dir ] {d}")

    # 2) 写基础文件（幂等）
    for rel, content in pkg.get("files", {}).items():
        _write_if_absent(root / rel, content, report)

    # 3) 新项目入口由根 AGENTS.md 承载；.claude/CLAUDE.md 只保留为旧项目 fallback，不默认生成。
    legacy_claude_md = root / ".claude" / "CLAUDE.md"
    if legacy_claude_md.exists():
        report.append(f"  [legacy-skip] {legacy_claude_md} 已存在（不作为 canonical 入口）")

    # 4) 写 topics/_seeds.md 提示文件（不是话题卡）
    _write_seeds_hint(root, pkg.get("roots", []), project_type, report)

    # 5) _tree.md 占位
    tree_md = root / "topics" / "_tree.md"
    if not tree_md.exists() and (root / "topics").exists():
        tree_md.write_text(
            "# 话题树\n\n> 由 `tree_gen.py` 生成，建话题后跑一次。\n",
            encoding="utf-8",
        )
        report.append(f"  [write] {tree_md}（占位，请跑 tree_gen.py）")

    # 6) Framework 文件（Vision/Structure/Style/Trace）
    # Framework 是项目级最高压缩层；新项目不再默认创建 001-004 基础话题，
    # 也不再把旧 doc/vision.md 等扁平文件作为主事实源。
    base_topics = pkg.get("base_topics", [])
    if base_topics:
        framework_dir = root / "doc" / "Framework"
        framework_dir.mkdir(parents=True, exist_ok=True)
        report.append("  [dir ] doc/Framework")

        framework_root_tmpl_path = templates_dir / "framework" / "Framework_README.md.tmpl"
        framework_file_tmpl_path = templates_dir / "framework" / "framework_file.md.tmpl"
        framework_readme_tmpl_path = templates_dir / "framework" / "README.md.tmpl"
        framework_root_tmpl = framework_root_tmpl_path.read_text(encoding="utf-8") if framework_root_tmpl_path.exists() else ""
        framework_file_tmpl = framework_file_tmpl_path.read_text(encoding="utf-8") if framework_file_tmpl_path.exists() else ""
        framework_readme_tmpl = framework_readme_tmpl_path.read_text(encoding="utf-8") if framework_readme_tmpl_path.exists() else ""

        if framework_root_tmpl:
            _write_if_absent(framework_dir / "README.md", _render(framework_root_tmpl, {}), report)

        for bt in base_topics:
            name = bt["name"]
            ctx = {
                "created": now_date(),
                "updated": now_date(),
                **render_framework_file_context(bt),
            }
            section_dir = framework_dir / name
            section_dir.mkdir(parents=True, exist_ok=True)
            report.append(f"  [dir ] {section_dir.relative_to(root)}")
            if framework_file_tmpl:
                _write_if_absent(root / framework_doc_path(name), _render(framework_file_tmpl, ctx), report)
            if framework_readme_tmpl:
                _write_if_absent(root / framework_readme_path(name), _render(framework_readme_tmpl, ctx), report)
            report.append(f"  [framework] {name}（由旧 base topic 语义迁移）")

    _write_project_cli_entries(root, project_type, report)
    return report, legacy


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def init_management_git(project_root: Path, report: list[str]) -> None:
    """在管理根初始化普通 Git；它只管理 Jiacong Flow 治理层。"""
    project_root = Path(project_root).resolve()
    if (project_root / ".git").exists():
        report.append("  [skip] .git 已存在（管理层 Git）")
        return

    git = shutil.which("git")
    if git is None:
        report.append("  [warn ] 未找到 git；跳过管理层 Git 初始化")
        return

    result = _run_git([git, "init"], project_root)
    if result.returncode == 0:
        report.append("  [git ] init .（管理层 Git）")
    else:
        report.append("  [warn ] git init . 失败：" + (result.stderr.strip() or result.stdout.strip()))


def _ensure_workspace_git(workspace_root: Path, main_name: str, report: list[str]) -> None:
    """创建 `.repo.git` bare repo 与 main worktree；失败时保留结构并报告。"""
    repo = workspace_root / ".repo.git"
    main_root = workspace_root / main_name
    git = shutil.which("git")
    if git is None:
        repo.mkdir(parents=True, exist_ok=True)
        main_root.mkdir(parents=True, exist_ok=True)
        report.append("  [warn ] 未找到 git；仅创建 workspace 目录骨架，worktree 管理不可用")
        return

    if not repo.exists():
        result = _run_git([git, "init", "--bare", str(repo)], workspace_root)
        if result.returncode == 0:
            report.append(f"  [git ] init --bare {repo}")
        else:
            repo.mkdir(parents=True, exist_ok=True)
            main_root.mkdir(parents=True, exist_ok=True)
            report.append(f"  [warn ] git init --bare 失败：{result.stderr.strip() or result.stdout.strip()}")
            return
    else:
        report.append(f"  [skip] {repo} 已存在")

    if (main_root / ".git").exists():
        report.append(f"  [skip] {main_root} 已是 git worktree")
        return

    if main_root.exists() and any(main_root.iterdir()):
        report.append(f"  [warn ] {main_root} 非空且不是 git worktree；跳过 git worktree add")
        return

    if main_root.exists():
        try:
            main_root.rmdir()
        except OSError:
            report.append(f"  [warn ] {main_root} 不是空目录；跳过 git worktree add")
            return

    first = _run_git([git, "--git-dir", str(repo), "worktree", "add", str(main_root), main_name], workspace_root)
    if first.returncode != 0:
        second = _run_git(
            [git, "--git-dir", str(repo), "worktree", "add", str(main_root), "-b", main_name],
            workspace_root,
        )
        if second.returncode != 0:
            main_root.mkdir(parents=True, exist_ok=True)
            report.append(
                "  [warn ] git worktree add 失败："
                + (second.stderr.strip() or second.stdout.strip() or first.stderr.strip() or first.stdout.strip())
            )
            return
    report.append(f"  [git ] worktree add {main_root}")


def _init_source_repo(project_root: Path, source_dir: str, use_git: bool, report: list[str]) -> None:
    """在项目根内初始化源码子仓库（子模块）；父仓库只管项目管理，子仓库推远程。"""
    if source_dir == ".":
        report.append("  [info] --source-dir=.，源码即项目根，跳过子仓库初始化")
        return

    source_path = project_root / source_dir
    source_path.mkdir(parents=True, exist_ok=True)
    report.append(f"  [dir ] {source_dir}/")

    if not use_git:
        report.append(f"  [info] --no-git，跳过 {source_dir}/.git 初始化")
        return

    if (source_path / ".git").exists():
        report.append(f"  [skip] {source_dir}/ 已是 git 仓库")
        return

    git = shutil.which("git")
    if git is None:
        report.append(f"  [warn ] 未找到 git；{source_dir}/ 子仓库初始化跳过")
        return

    result = _run_git([git, "init", str(source_path)], project_root)
    if result.returncode == 0:
        report.append(f"  [git ] init {source_dir}/（源码子仓库）")
    else:
        report.append(
            f"  [warn ] git init {source_dir}/ 失败："
            + (result.stderr.strip() or result.stdout.strip())
        )


def _write_source_state(project_root: Path, payload: dict, report: list[str]) -> None:
    """原子写入源码层状态；source.json 是成功标记。"""
    state_path = project_root / ".jiacong" / "source.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(state_path)
    report.append(f"  [write] {state_path}")


def _ensure_source_workspace_git(source_workspace: Path, main_name: str, report: list[str]) -> None:
    """创建源码层 bare repo 与 main worktree；失败抛出异常，由调用方清理本次创建内容。"""
    repo = source_workspace / ".repo.git"
    main_root = source_workspace / main_name
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("未找到 git，无法初始化源码层 workspace")

    result = _run_git([git, "init", "--bare", str(repo)], source_workspace)
    if result.returncode != 0:
        raise RuntimeError("git init --bare 失败：" + (result.stderr.strip() or result.stdout.strip()))
    report.append(f"  [git ] init --bare {repo}（源码层 workspace）")

    first = _run_git([git, "--git-dir", str(repo), "worktree", "add", str(main_root), main_name], source_workspace)
    if first.returncode != 0:
        second = _run_git([git, "--git-dir", str(repo), "worktree", "add", str(main_root), "-b", main_name], source_workspace)
        if second.returncode != 0:
            raise RuntimeError(
                "git worktree add 失败："
                + (second.stderr.strip() or second.stdout.strip() or first.stderr.strip() or first.stdout.strip())
            )
    report.append(f"  [git ] worktree add {main_root}（源码层 main）")


def _validate_safe_relative_path(raw: str, *, name: str) -> str:
    """初始化参数路径校验：只允许项目内安全相对路径。"""
    value = str(raw or "").strip().strip("/")
    if not value or value == ".":
        return "." if name == "source_dir" else (_raise_path_error(name, raw))
    path = Path(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        _raise_path_error(name, raw)
    return value


def _raise_path_error(name: str, raw: object) -> str:
    raise SystemExit(f"[错误] {name} 只能是项目内安全相对路径，不能为空、绝对路径或包含 '..'：{raw}")


def init_source_workspace(
    project_root: Path,
    *,
    source_root: str = "source",
    source_dir: str = "app",
    source_main_name: str = "main",
    use_git: bool = True,
    report: list[str],
) -> None:
    """在管理根下初始化源码层 workspace；不写 topics/logs/.jiacong 到源码 worktree。"""
    project_root = Path(project_root).resolve()
    source_root = _validate_safe_relative_path(source_root, name="source_root")
    source_dir = _validate_safe_relative_path(source_dir, name="source_dir")
    source_main_name = _validate_safe_relative_path(source_main_name, name="source_main_name")
    if source_dir == ".":
        raise SystemExit("[错误] --source-workspace 模式下 --source-dir 不能为 '.'；源码内容目录必须位于源码 worktree 内的具体子目录。")
    source_workspace = project_root / source_root
    if source_workspace.exists():
        raise SystemExit(f"[错误] 源码层目录已存在，停止以避免覆盖：{source_workspace}")

    created_source = False
    try:
        source_workspace.mkdir(parents=True)
        created_source = True
        report.append(f"  [dir ] {source_root}/（源码 workspace 容器）")
        (source_workspace / "worktrees").mkdir(parents=True, exist_ok=True)
        report.append(f"  [dir ] {source_root}/worktrees")

        if use_git:
            _ensure_source_workspace_git(source_workspace, source_main_name, report)
        else:
            (source_workspace / source_main_name).mkdir(parents=True, exist_ok=True)
            report.append(f"  [dir ] {source_root}/{source_main_name}（源码 main，无 git）")

        content_root = source_workspace / source_main_name / source_dir
        content_root.mkdir(parents=True, exist_ok=True)
        report.append(f"  [dir ] {source_root}/{source_main_name}/{source_dir}/（源码内容目录）")

        now = datetime.now().isoformat(timespec="seconds")
        payload = {
            "schema_version": 1,
            "mode": "source_workspace",
            "git_enabled": bool(use_git),
            "source_root": source_root,
            "repo_git_path": f"{source_root}/.repo.git",
            "worktrees_root": f"{source_root}/worktrees",
            "main_name": source_main_name,
            "source_dir": source_dir,
            "updated_at": now,
        }
        _write_source_state(project_root, payload, report)
    except Exception:
        if created_source:
            shutil.rmtree(source_workspace, ignore_errors=True)
        raise


def init_workspace_root(
    workspace_root: Path,
    project_type: str,
    *,
    main_name: str = "main",
    source_dir: str = "app",
    use_git: bool = True,
    adopt_existing: bool = False,
) -> tuple[list[str], list[str]]:
    """初始化 workspace 容器，并把 main worktree 初始化为第一项目根。"""
    workspace_root = Path(workspace_root).resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    if _has_project_root_payload(workspace_root):
        raise SystemExit(
            "[错误] 当前目录已存在 .claude/topics/logs 等项目根痕迹，"
            "不能直接作为 workspace 容器初始化；请在父目录新建 workspace，"
            "或先把既有项目内容迁移到 main/ 后再初始化。"
        )
    payload = _collect_adoptable_payload(workspace_root, main_name) if adopt_existing else []
    report: list[str] = [
        f"[workspace] 容器根：{workspace_root}",
        f"[workspace] main worktree：{main_name}",
    ]

    if use_git:
        _ensure_workspace_git(workspace_root, main_name, report)
    else:
        (workspace_root / ".repo.git").mkdir(parents=True, exist_ok=True)
        (workspace_root / main_name).mkdir(parents=True, exist_ok=True)
        report.append("  [dir ] .repo.git（结构模式）")
        report.append(f"  [dir ] {main_name}")

    if adopt_existing:
        _adopt_existing_payload(payload, workspace_root / main_name, report)

    (workspace_root / "worktrees").mkdir(parents=True, exist_ok=True)
    report.append("  [dir ] worktrees")
    _write_workspace_cli_entries(workspace_root, main_name, report)

    state_dir = workspace_root / ".jiacong-workspace"
    state_dir.mkdir(parents=True, exist_ok=True)
    current = state_dir / "current-worktree"
    if not current.exists():
        current.write_text(f"{main_name}\n", encoding="utf-8")
        report.append(f"  [write] {current}")
    else:
        report.append(f"  [skip] {current}")
    meta = state_dir / "current-worktree.json"
    if not meta.exists():
        payload = {
            "active": main_name,
            "branch": main_name,
            "path": str((workspace_root / main_name).resolve()),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "managed": True,
        }
        meta.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report.append(f"  [write] {meta}")
    else:
        report.append(f"  [skip] {meta}")

    project_report, legacy = init_project_root(workspace_root / main_name, project_type)
    report.extend(project_report)

    _init_source_repo(workspace_root / main_name, source_dir, use_git, report)

    return report, legacy


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="按架构套餐初始化项目脚手架。")
    parser.add_argument("root", help="项目根目录或 workspace 容器根")
    parser.add_argument(
        "--type",
        required=True,
        choices=["学术", "实证", "代码", "短平快"],
        help="架构套餐类型",
    )
    parser.add_argument(
        "--workspace",
        action="store_true",
        help="legacy 管理层 workspace 容器模式：外层容器 + main/ 项目根 + worktrees/；新项目默认优先使用 --init-management-git + --source-workspace",
    )
    parser.add_argument(
        "--main-name",
        default="main",
        help="workspace 模式下主 worktree 目录/分支名，默认 main",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="workspace 模式下只创建目录骨架，不执行 git init/worktree add",
    )
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="workspace 模式下把外层已有历史文件移动进 main/；仅支持无 .git、无 .claude/topics/logs 的普通目录",
    )
    parser.add_argument(
        "--source-dir",
        default="app",
        help="源码目录名。legacy --workspace 下为 main/ 内源码子仓库；--source-workspace 下为源码 worktree 内内容目录，默认 app。设为 '.' 表示项目根即源码根",
    )
    parser.add_argument(
        "--init-management-git",
        action="store_true",
        help="在项目根初始化普通 .git 作为管理层 Git，管理 .jiacong/topics/logs/doc/Framework 等治理材料",
    )
    parser.add_argument(
        "--dual-git",
        action="store_true",
        help="启用推荐双 Git 组合：等价于 --init-management-git --source-workspace",
    )
    parser.add_argument(
        "--source-workspace",
        action="store_true",
        help="按源码层 workspace 模式初始化：当前 root 为管理根，源码 worktree 容器放在 root/source/",
    )
    parser.add_argument(
        "--source-root",
        default="source",
        help="--source-workspace 模式下源码 workspace 容器目录名，默认 source",
    )
    parser.add_argument(
        "--source-main-name",
        default="main",
        help="--source-workspace 模式下源码 main worktree 名，默认 main",
    )
    parser.add_argument(
        "--no-source-git",
        action="store_true",
        help="--source-workspace 模式下只创建源码目录骨架，不初始化源码层 git/worktree",
    )
    args = parser.parse_args()

    if args.dual_git:
        args.init_management_git = True
        args.source_workspace = True

    if args.workspace and args.source_workspace:
        print("[错误] --workspace 与 --source-workspace/--dual-git 互斥：前者是 legacy 管理层 workspace，后者是管理根下源码层 workspace。")
        return 2

    if args.workspace and args.init_management_git:
        print("[错误] --workspace 与 --init-management-git 互斥：legacy workspace 的管理层 Git 位于外层 .repo.git，不再叠加普通管理根 .git。")
        return 2

    if args.workspace:
        next_project_root = Path(args.root).resolve() / args.main_name
        report, legacy = init_workspace_root(
            Path(args.root),
            args.type,
            main_name=args.main_name,
            source_dir=args.source_dir,
            use_git=not args.no_git,
            adopt_existing=args.adopt_existing,
        )
    else:
        next_project_root = Path(args.root).resolve()
        report, legacy = init_project_root(Path(args.root), args.type, skip_source_dirs=args.source_workspace)
        if args.init_management_git:
            init_management_git(next_project_root, report)
        if args.source_workspace:
            init_source_workspace(
                next_project_root,
                source_root=args.source_root,
                source_dir=args.source_dir,
                source_main_name=args.source_main_name,
                use_git=not args.no_source_git,
                report=report,
            )

    print("\n".join(report))
    if legacy:
        print("\n".join(legacy))
    print(f"\n[done] 初始化完成。下一步建议：")
    print(f"  1. 生成树视图：python tree_gen.py {next_project_root}")
    print(f"  2. 启动仪表盘：python dashboard.py {next_project_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
