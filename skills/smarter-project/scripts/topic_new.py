# -*- coding: utf-8 -*-
"""
topic_new.py · 新建话题（三件套：scratch.md + card.md[+tasks.md][+template.md]）

用法：
    python topic_new.py <项目根> <简称> --parent <父ID|null> --root <根类emoji标签>
                       [--with-tasks] [--with-template] [--id <NNN>] [--note "初始备注"]

示例：
    python topic_new.py D:/proj 脚本工具链 --parent 100 --root 🛠️管理

行为：
    - 自动分配 NNN（当前最大+1），也可 --id 指定
    - 建立 topics/NNN_简称/ 目录
    - 渲染 scratch.md + card.md；可选渲染 tasks.md / template.md
    - 刷新 _tree.md（调用 tree_gen 逻辑）
    - 幂等：若 NNN_简称 已存在则报错退出
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
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
    render_template as _render,
    render_template_context,
    render_toc_context,
)
from _lib.topics_loader import load_topics  # noqa: E402
from _lib.journal import log_created  # noqa: E402


_SLUG_RE = re.compile(r"^(\d{3})_(.+)$")


def _next_id(root: Path) -> str:
    """扫描 topics/ 取最大编号+1，格式化为 3 位。"""
    topics_dir = root / "topics"
    max_n = 0
    if topics_dir.exists():
        for d in topics_dir.iterdir():
            if not d.is_dir():
                continue
            m = _SLUG_RE.match(d.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return f"{max_n + 1:03d}"


def _validate_parent(root: Path, parent: str | None) -> str:
    """校验父话题存在；允许 'null'/空。返回规范化的 parent 值。"""
    if parent is None or parent.lower() in ("null", "none", ""):
        return "null"
    # parent 可以是 NNN 或 NNN_简称
    topics_dir = root / "topics"
    for d in topics_dir.iterdir() if topics_dir.exists() else []:
        if not d.is_dir():
            continue
        m = _SLUG_RE.match(d.name)
        if m and (m.group(1) == parent or d.name == parent):
            return d.name
    raise SystemExit(f"[错误] 父话题不存在：{parent}")


def _call_tree_gen(root: Path) -> None:
    """调用同目录的 tree_gen.py 刷新 _tree.md；失败则给提示但不崩溃。"""
    tree_gen = Path(__file__).parent / "tree_gen.py"
    if not tree_gen.exists():
        print("[提示] tree_gen.py 不存在，跳过 _tree.md 刷新")
        return
    try:
        subprocess.run(
            [sys.executable, str(tree_gen), str(root)],
            check=False,
            capture_output=True,
        )
    except Exception as e:
        print(f"[提示] 调用 tree_gen.py 失败：{e}")


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="新建话题三件套。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("short_name", help="话题简称（2-6字中文或小写英文）")
    parser.add_argument("--parent", default="null", help="父话题 NNN 或 NNN_简称")
    parser.add_argument("--root", "--root-label", dest="root_label",
                        default="", help="根类标签，如 🎯目标")
    parser.add_argument("--id", dest="topic_num", default=None,
                        help="手动指定 NNN（默认自动分配）")
    parser.add_argument("--note", default="", help="scratch 初始备注")
    parser.add_argument("--with-tasks", action="store_true",
                        help="同时建立 tasks.md")
    parser.add_argument("--with-template", action="store_true",
                        help="同时建立 template.md 第四组件")
    parser.add_argument("--template-profile", default="generic",
                        help="template.md 使用的模板 profile，默认 generic")
    parser.add_argument("--role", default="", help="关联角色 ID")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    topics_dir = root / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)

    # 预热一次缓存（顺带保证 .cache 目录结构存在）
    load_topics(root)

    nnn = args.topic_num or _next_id(root)
    if not re.match(r"^\d{3}$", nnn):
        raise SystemExit(f"[错误] --id 必须是 3 位数字：{nnn}")

    slug = f"{nnn}_{args.short_name}"
    topic_dir = topics_dir / slug
    if topic_dir.exists():
        raise SystemExit(f"[错误] 话题目录已存在：{topic_dir}")

    parent_val = _validate_parent(root, args.parent)
    parent_link = "—" if parent_val == "null" else f"[[{parent_val}]]"

    templates_dir = find_templates_dir(__file__)
    topic_dir.mkdir(parents=True)

    # scratch.md
    scratch_tmpl = (templates_dir / "topic" / "scratch.md.tmpl").read_text(
        encoding="utf-8"
    )
    scratch_ctx = {
        "topic_id": slug,
        "parent": parent_val,
        "root": args.root_label,
        "status": "💭 讨论中",
        "created": now_date(),
        "created_ts": now_datetime(),
        "topic_name": args.short_name,
        "initial_note": args.note,
    }
    (topic_dir / "scratch.md").write_text(
        _render(scratch_tmpl, scratch_ctx), encoding="utf-8"
    )

    # card.md
    card_tmpl = (templates_dir / "topic" / "card.md.tmpl").read_text(
        encoding="utf-8"
    )
    card_ctx = {
        "topic_id": slug,
        "parent": parent_val,
        "root": args.root_label,
        "created": now_date(),
        "title": args.short_name,
        "parent_link": parent_link,
        "role": args.role,
        **render_toc_context(),
    }
    (topic_dir / "card.md").write_text(
        _render(card_tmpl, card_ctx), encoding="utf-8"
    )

    # tasks.md（可选）
    if args.with_tasks:
        tasks_tmpl = (templates_dir / "topic" / "tasks.md.tmpl").read_text(
            encoding="utf-8"
        )
        tasks_ctx = {
            "topic_id": slug,
            "created": now_date(),
            "topic_name": args.short_name,
        }
        (topic_dir / "tasks.md").write_text(
            _render(tasks_tmpl, tasks_ctx), encoding="utf-8"
        )

    # template.md（可选）
    if args.with_template:
        template_tmpl = (templates_dir / "topic" / "template.md.tmpl").read_text(
            encoding="utf-8"
        )
        template_ctx = {
            "created": now_date(),
            "updated": now_date(),
            **render_template_context(args.short_name, args.template_profile),
        }
        (topic_dir / "template.md").write_text(
            _render(template_tmpl, template_ctx), encoding="utf-8"
        )

    # flow-log 记录：话题创建事件（只记显式信号）
    try:
        log_created(root, slug, source="topic_new")
    except Exception as e:
        print(f"[提示] flow-log 写入失败：{e}")

    print(f"[ok] 新话题已建立：{topic_dir}")
    print(f"  - scratch.md")
    print(f"  - card.md")
    if args.with_tasks:
        print(f"  - tasks.md")
    if args.with_template:
        print(f"  - template.md")

    _call_tree_gen(root)
    print(f"[next] 建议：正文写入走 card_write.py --section <N> --mode integrate|replace")
    return 0


if __name__ == "__main__":
    sys.exit(main())
