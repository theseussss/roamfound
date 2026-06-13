# -*- coding: utf-8 -*-
"""
topics_loader · B1 §4.3 的 E 方案实现（re-export 层）

实现已迁入 data.py，本模块保留公开接口不变。

parse_md 返回字段结构：
    {
        "mtime": float,
        "frontmatter": dict,
        "toc": [{"level": int, "num": str, "title": str, "intent": str, ...}, ...],
        "sections": [{"level": int, "num": str, "title": str, "heading": str, ...}, ...],
        "links": [str, ...],
        "path": str,
        "slug": str,
    }
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from .data import (  # noqa: F401
        parse_frontmatter_simple as _parse_frontmatter,
        parse_md,
        find_cards,
        load_cache,
        save_cache,
        load_topics,
        load_topics_by_slug,
    )
except ImportError:
    from data import (  # type: ignore  # noqa: F401
        parse_frontmatter_simple as _parse_frontmatter,
        parse_md,
        find_cards,
        load_cache,
        save_cache,
        load_topics,
        load_topics_by_slug,
    )


# --------------------------------------------------------------------------- #
# CLI 自检
# --------------------------------------------------------------------------- #

def _main() -> int:
    """独立运行时：`python topics_loader.py <项目根>` 打印摘要。"""
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if len(sys.argv) < 2:
        print("用法：python topics_loader.py <项目根>")
        return 1
    root = Path(sys.argv[1])
    topics = load_topics(root)
    print(f"共解析话题卡 {len(topics)} 张")
    for data in topics.values():
        fm = data["frontmatter"]
        print(f"  - {data['slug']:20s} [{fm.get('status', '?')}] "
              f"TOC {len(data['toc'])} 条，章节 {len(data['sections'])} 个，"
              f"链接 {len(data['links'])} 个")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
