# -*- coding: utf-8 -*-
"""
check_links.py · 扫描 [[NNN_简称]] 引用 + frontmatter.parent 断链

用法：
    python check_links.py <项目根> [--json]

行为：
    - 基于 load_topics() 取全量 links + parent
    - 同时扫 topics/_tree.md 中的 [[...]] 引用（可选扩展）
    - 输出断链列表；按规范打印或 JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.topics_loader import load_topics  # noqa: E402


def scan_links(root: Path) -> dict:
    topics = load_topics(root)
    by_slug = {t["slug"]: t for t in topics.values()}
    short_to_slug = {
        t["slug"].split("_", 1)[0]: t["slug"] for t in topics.values() if "_" in t["slug"]
    }

    broken_parent: list[dict] = []
    broken_link: list[dict] = []
    for data in topics.values():
        fm = data["frontmatter"]
        parent = fm.get("parent")
        if parent and parent not in ("null", "None", None):
            if parent not in by_slug and parent not in short_to_slug:
                broken_parent.append({
                    "source": data["slug"],
                    "target": parent,
                    "kind": "frontmatter.parent",
                })
        for link in data["links"]:
            if link not in by_slug and link not in short_to_slug:
                broken_link.append({
                    "source": data["slug"],
                    "target": link,
                    "kind": "[[]]",
                })

    # 扫 _tree.md
    tree_md = root / "topics" / "_tree.md"
    tree_broken: list[dict] = []
    if tree_md.exists():
        import re
        text = tree_md.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", text):
            target = m.group(1)
            if target not in by_slug and target not in short_to_slug:
                tree_broken.append({
                    "source": "topics/_tree.md",
                    "target": target,
                    "kind": "[[]]",
                })
    return {
        "broken_parent": broken_parent,
        "broken_link": broken_link,
        "tree_broken": tree_broken,
        "total": len(broken_parent) + len(broken_link) + len(tree_broken),
    }


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="扫描断链。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    result = scan_links(root)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"断链扫描：{root}")
    print(f"  parent 断链：{len(result['broken_parent'])}")
    print(f"  [[]] 断链：  {len(result['broken_link'])}")
    print(f"  _tree 断链： {len(result['tree_broken'])}")
    print(f"  合计：       {result['total']}")
    if result["total"] == 0:
        print("[ok] 无断链")
        return 0

    print()
    for b in result["broken_parent"]:
        print(f"  [parent] {b['source']} → {b['target']}")
    for b in result["broken_link"]:
        print(f"  [[]]    {b['source']} → {b['target']}")
    for b in result["tree_broken"]:
        print(f"  [tree]  {b['source']} → {b['target']}")
    return 1 if result["total"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
