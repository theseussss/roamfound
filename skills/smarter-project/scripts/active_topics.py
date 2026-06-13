# -*- coding: utf-8 -*-
"""
active_topics.py · 列出活跃话题（按 updated 排序）

用法：
    python active_topics.py <项目根> [--days N] [--limit N] [--json]

行为：
    - 从 load_topics() 拿全量
    - 过滤掉终态（✅ ⏸️ 🔻 🗑️），只留 ⏳
    - 默认按 updated 倒序，取前 N 条
    - 每条输出：slug | 状态 | 根类 | 更新时间 | 面包屑
    - 可选 --json 输出给 dashboard.py 消费
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.topics_loader import load_topics  # noqa: E402


_TERMINAL_STATUSES = {"✅", "⏸️", "🔻", "🗑️"}


def _status_emoji(s: str) -> str:
    if not s:
        return "⏳"
    parts = s.strip().split()
    return parts[0] if parts else "⏳"


def _parse_dt(s: str) -> datetime | None:
    """宽松解析时间字符串。"""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _build_breadcrumb(slug: str, by_slug: dict, short_to_slug: dict) -> str:
    """逆向追溯 parent 链。"""
    chain = []
    cur = slug
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        node = by_slug.get(cur)
        if not node:
            break
        short_id = node["slug"].split("_", 1)[0] if "_" in node["slug"] else node["slug"]
        title = node["slug"].split("_", 1)[-1] if "_" in node["slug"] else node["slug"]
        chain.append(f"{short_id} {title}")
        parent = node["frontmatter"].get("parent")
        if not parent or parent in ("null", "None", None):
            break
        cur = parent if parent in by_slug else short_to_slug.get(parent, "")
    return " > ".join(reversed(chain))


def compute_active(root: Path, days: int, limit: int) -> list[dict]:
    """返回活跃话题列表（给 dashboard 复用）。"""
    topics = load_topics(root)
    by_slug = {t["slug"]: t for t in topics.values()}
    short_to_slug = {
        t["slug"].split("_", 1)[0]: t["slug"] for t in topics.values() if "_" in t["slug"]
    }

    cutoff = datetime.now() - timedelta(days=days) if days > 0 else None
    items: list[dict] = []
    for data in topics.values():
        fm = data["frontmatter"]
        status = _status_emoji(fm.get("status", ""))
        if status in _TERMINAL_STATUSES:
            continue
        updated_str = fm.get("updated") or fm.get("created", "")
        dt = _parse_dt(updated_str)
        if cutoff and dt and dt < cutoff:
            continue
        items.append({
            "slug": data["slug"],
            "status": status,
            "root": fm.get("root", ""),
            "updated": updated_str,
            "updated_dt": dt,
            "breadcrumb": _build_breadcrumb(data["slug"], by_slug, short_to_slug),
        })

    items.sort(key=lambda x: x["updated_dt"] or datetime.min, reverse=True)
    if limit > 0:
        items = items[:limit]
    return items


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="列出活跃话题。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("--days", type=int, default=7, help="近 N 天（0=不限制）")
    parser.add_argument("--limit", type=int, default=10, help="最多返回条数（0=全部）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    items = compute_active(root, args.days, args.limit)

    if args.json:
        # JSON 输出时剥离 datetime 对象
        out = [{k: v for k, v in it.items() if k != "updated_dt"} for it in items]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if not items:
        print(f"[info] 近 {args.days} 天无活跃话题")
        return 0

    print(f"活跃话题（近 {args.days} 天，Top {args.limit}）")
    print(f"{'状态':<4} {'slug':<24} {'更新':<18} 面包屑")
    print("-" * 80)
    for it in items:
        print(f"{it['status']:<4} {it['slug']:<24} {it['updated']:<18} {it['breadcrumb']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
