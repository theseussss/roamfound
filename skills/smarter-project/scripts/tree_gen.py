# -*- coding: utf-8 -*-
"""
tree_gen.py · 生成 topics/_tree.md（mermaid + ASCII + 节点明细表）

用法：
    python tree_gen.py <项目根>

行为：
    - 调用 load_topics() 取全量话题
    - 按 frontmatter.parent 构建森林
    - 渲染 _tree.md.tmpl → topics/_tree.md
    - 幂等
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import (  # noqa: E402
    configure_stdout_utf8,
    ensure_project_root,
    now_datetime,
)
from _lib.store import find_templates_dir  # noqa: E402
from _lib.topics_loader import load_topics  # noqa: E402

try:
    from jinja2 import Template  # type: ignore
    _HAS_JINJA = True
except ImportError:
    _HAS_JINJA = False


_TERMINAL_STATUSES = {"✅", "⏸️", "🔻", "🗑️"}


def _extract_status_emoji(status_str: str) -> str:
    """从 'status: ⏳ 进行中' 这样的值里取出 emoji。"""
    if not status_str:
        return "⏳"
    s = status_str.strip()
    # 取首个非空白字符块
    return s.split()[0] if s.split() else "⏳"


def _read_scratch_status(card_path: str) -> str:
    """
    从同目录 scratch.md 的 frontmatter 读 status emoji。
    独立于 topics_loader（loader 只解析 card.md），不动 loader 架构。
    读不到或无 scratch.md 返回空字符串。
    """
    scratch_path = Path(card_path).parent / "scratch.md"
    if not scratch_path.exists():
        return ""
    try:
        with open(scratch_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    # 最小化 YAML frontmatter 解析
    if not text.startswith("---"):
        return ""
    lines = text.split("\n")
    for i in range(1, len(lines)):
        ln = lines[i].rstrip()
        if ln == "---":
            break
        if ":" not in ln:
            continue
        k, _, v = ln.partition(":")
        if k.strip() == "status":
            return _extract_status_emoji(v.strip().strip('"').strip("'"))
    return ""


def _extract_root_emoji(root_str: str) -> str:
    """从 '🎯目标' 中取 emoji。"""
    if not root_str:
        return ""
    # 取首字符（可能是复合 emoji，简化处理）
    m = re.match(r"^(\S+?)([\u4e00-\u9fff].*)?$", root_str.strip())
    if m:
        return m.group(1)
    return root_str.strip()[:2]


def _build_nodes(topics: dict) -> tuple[list[dict], list[dict]]:
    """返回 (nodes, edges)。"""
    nodes: list[dict] = []
    edges: list[dict] = []
    for data in topics.values():
        fm = data["frontmatter"]
        slug = data["slug"]
        status = _extract_status_emoji(fm.get("status", "⏳"))
        root = fm.get("root", "")
        title = slug.split("_", 1)[-1] if "_" in slug else slug
        short_id = slug.split("_", 1)[0] if "_" in slug else slug
        # mermaid 节点 id 必须是纯字母数字，用 n + NNN
        node_id = "n" + re.sub(r"\D", "", short_id) if re.search(r"\d", short_id) else "n" + slug
        scratch_status = _read_scratch_status(data["path"])
        node = {
            "id": node_id,
            "short_id": short_id,
            "slug": slug,
            "title": title,
            "emoji": _extract_root_emoji(root),
            "root_emoji": _extract_root_emoji(root),
            "root_label": root.strip() if root else "(未分组)",
            "status": status,
            "scratch_status": scratch_status,
            "parent": fm.get("parent") if fm.get("parent") not in (None, "null", "None") else None,
            "updated": fm.get("updated", fm.get("created", "")),
        }
        nodes.append(node)

    slug_to_id = {n["slug"]: n["id"] for n in nodes}
    short_to_slug = {n["short_id"]: n["slug"] for n in nodes}

    for n in nodes:
        parent = n["parent"]
        if not parent:
            continue
        parent_slug = parent if parent in slug_to_id else short_to_slug.get(parent)
        if parent_slug and parent_slug in slug_to_id:
            edges.append({"parent": slug_to_id[parent_slug], "child": n["id"]})
    return nodes, edges


def _build_root_groups(nodes: list[dict]) -> list[dict]:
    """
    C 方案：按 frontmatter.root 字段分组（不再有"根话题"）。
    返回 groups 列表，每组含标签 + 本组话题 ASCII 子树。
    """
    by_slug = {n["slug"]: n for n in nodes}
    short_to_slug = {n["short_id"]: n["slug"] for n in nodes}

    # 按 root_label 分组
    groups_map: dict[str, list[dict]] = {}
    for n in nodes:
        groups_map.setdefault(n["root_label"], []).append(n)

    def render_group_subtree(group_nodes: list[dict]) -> list[str]:
        """在 group 范围内按 parent 构建局部森林并渲染 ASCII。"""
        group_slugs = {n["slug"] for n in group_nodes}
        children: dict[str, list[str]] = {}
        local_roots: list[str] = []
        for n in group_nodes:
            parent = n["parent"]
            if not parent:
                local_roots.append(n["slug"])
                continue
            parent_slug = parent if parent in by_slug else short_to_slug.get(parent)
            # 父节点不在本 group → 当作本 group 局部根
            if not parent_slug or parent_slug not in group_slugs:
                local_roots.append(n["slug"])
                continue
            children.setdefault(parent_slug, []).append(n["slug"])

        for k in children:
            children[k].sort()
        local_roots.sort()

        def render_node(slug: str, prefix: str, is_last: bool) -> list[str]:
            node = by_slug[slug]
            connector = "└── " if is_last else "├── "
            lines = [
                f"{prefix}{connector}{node['short_id']} "
                f"{node['title']}  [{node['status']}"
                + (f" · {node['scratch_status']}" if node['scratch_status'] else "")
                + "]"
            ]
            next_prefix = prefix + ("    " if is_last else "│   ")
            kids = children.get(slug, [])
            for i, kid in enumerate(kids):
                lines.extend(render_node(kid, next_prefix, i == len(kids) - 1))
            return lines

        out: list[str] = []
        for i, root_slug in enumerate(local_roots):
            out.extend(render_node(root_slug, "", i == len(local_roots) - 1))
        return out

    # 排序：按 root_label 的首字符（emoji）排
    sorted_labels = sorted(groups_map.keys())
    result = []
    for label in sorted_labels:
        gn = groups_map[label]
        active = sum(1 for n in gn if n["status"] not in _TERMINAL_STATUSES)
        result.append({
            "root_label": label,
            "root_emoji": _extract_root_emoji(label),
            "count": len(gn),
            "active_count": active,
            "subtree_ascii": render_group_subtree(gn),
        })
    return result


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="生成 topics/_tree.md。")
    parser.add_argument("root", help="项目根目录")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    topics = load_topics(root)
    nodes, edges = _build_nodes(topics)
    groups = _build_root_groups(nodes)

    nodes_sorted = sorted(nodes, key=lambda n: n["short_id"])
    terminal_count = sum(1 for n in nodes if n["status"] in _TERMINAL_STATUSES)
    active_count = len(nodes) - terminal_count

    # 确定 project_type（若有 CLAUDE.md 可从中推断，这里留待扩展）
    project_type = "—"

    templates_dir = find_templates_dir(__file__)
    tmpl_path = templates_dir / "topic" / "_tree.md.tmpl"
    if not tmpl_path.exists():
        print(f"[错误] 模板不存在：{tmpl_path}", file=sys.stderr)
        return 1

    tmpl_text = tmpl_path.read_text(encoding="utf-8")
    ctx = {
        "generated_at": now_datetime(),
        "project_type": project_type,
        "nodes_total": len(nodes),
        "nodes_active": active_count,
        "nodes_terminal": terminal_count,
        "nodes": nodes,
        "edges": edges,
        "groups": groups,
        "nodes_sorted": nodes_sorted,
    }

    if not _HAS_JINJA:
        print("[错误] tree_gen.py 需要 jinja2；请 pip install jinja2", file=sys.stderr)
        return 2

    output = Template(tmpl_text, keep_trailing_newline=True).render(**ctx)
    out_path = root / "topics" / "_tree.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"[ok] {out_path} （节点 {len(nodes)}，边 {len(edges)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
