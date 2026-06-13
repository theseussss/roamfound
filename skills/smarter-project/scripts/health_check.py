# -*- coding: utf-8 -*-
"""
health_check.py · 项目健康指标

用法：
    python health_check.py <项目根> [--json]

检查项（见 SKILL.md §2.2 记录机制 + §2.1 话题（三位一体状态流）+ references/topic-lifecycle.md §5.2）：
    1. 流水阈值：logs/stream.md 行数>500 或大小>100KB 提示切分
    2. 项目入口更新时效：AGENTS.md 近 30 天未动则告警（项目入口应定期回顾）
    3. card 结构：每张 card 的 TOC 存在性 / 与正文章节对齐（粗粒度）
    4. 断链数：frontmatter.parent 和 [[链接]] 中的断链计数
    5. status 字段规约：话题卡 status 必须是完整字符串（emoji + 空格 + 中文）
    6. 话题五态分布（信息性）
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
from _lib.guard import check_card_structure, warn_only  # noqa: E402


STREAM_LINES_THRESHOLD = 500
STREAM_SIZE_THRESHOLD = 100 * 1024
VISION_STALE_DAYS = 30


def _check_stream(root: Path) -> dict:
    stream = root / "logs" / "stream.md"
    if not stream.exists():
        return {"exists": False, "warn": False, "msg": "logs/stream.md 不存在"}
    text = stream.read_text(encoding="utf-8", errors="replace")
    lines = text.count("\n") + 1
    size = stream.stat().st_size
    warn = lines > STREAM_LINES_THRESHOLD or size > STREAM_SIZE_THRESHOLD
    return {
        "exists": True,
        "lines": lines,
        "size": size,
        "warn": warn,
        "msg": (
            f"流水行数 {lines}（阈值 {STREAM_LINES_THRESHOLD}）"
            f"，大小 {size}B（阈值 {STREAM_SIZE_THRESHOLD}B）"
            + ("，建议切分 stream_YYYY-MM.md" if warn else "")
        ),
    }


def _project_entry_path(root: Path) -> Path | None:
    agents = root / "AGENTS.md"
    if agents.exists():
        return agents
    legacy = root / ".claude" / "CLAUDE.md"
    if legacy.exists():
        return legacy
    return None


def _check_vision(root: Path) -> dict:
    entry = _project_entry_path(root)
    if entry is None:
        return {"exists": False, "warn": True, "msg": "AGENTS.md 不存在（旧 .claude/CLAUDE.md fallback 也不存在）"}
    mtime = datetime.fromtimestamp(entry.stat().st_mtime)
    days = (datetime.now() - mtime).days
    warn = days > VISION_STALE_DAYS
    rel = entry.relative_to(root).as_posix()
    return {
        "exists": True,
        "path": rel,
        "days_since_update": days,
        "warn": warn,
        "msg": f"{rel} 上次更新 {days} 天前"
               + ("，项目入口应定期回顾" if warn else ""),
    }


def _check_card_structure(topics: dict) -> dict:
    no_toc: list[str] = []
    mismatch: list[str] = []
    for data in topics.values():
        if not data["toc"]:
            no_toc.append(data["slug"])
            continue
        warns = warn_only(check_card_structure(data["toc"], data["sections"]))
        if warns:
            codes = ", ".join(w["code"] for w in warns)
            mismatch.append(f"{data['slug']}（{codes}）")
    return {
        "total": len(topics),
        "no_toc": no_toc,
        "mismatch": mismatch,
        "warn": bool(no_toc or mismatch),
        "msg": f"无 TOC 卡片：{len(no_toc)}；TOC 与正文不对齐：{len(mismatch)}",
    }


def _check_links(topics: dict) -> dict:
    by_slug = {t["slug"]: t for t in topics.values()}
    short_to_slug = {
        t["slug"].split("_", 1)[0]: t["slug"] for t in topics.values() if "_" in t["slug"]
    }
    broken_parent: list[str] = []
    broken_link: list[str] = []
    for data in topics.values():
        fm = data["frontmatter"]
        parent = fm.get("parent")
        if parent and parent not in ("null", "None", None):
            if parent not in by_slug and parent not in short_to_slug:
                broken_parent.append(f"{data['slug']} → {parent}")
        for link in data["links"]:
            if link not in by_slug and link not in short_to_slug:
                broken_link.append(f"{data['slug']} → [[{link}]]")
    total = len(broken_parent) + len(broken_link)
    return {
        "broken_parent": broken_parent,
        "broken_link": broken_link,
        "total": total,
        "warn": total > 0,
        "msg": f"断链总计 {total}（parent {len(broken_parent)} + [[]] {len(broken_link)}）",
    }


def _check_status_distribution(topics: dict) -> dict:
    dist: dict[str, int] = {}
    for data in topics.values():
        s = data["frontmatter"].get("status", "⏳").strip().split()[0] if data["frontmatter"].get("status") else "⏳"
        dist[s] = dist.get(s, 0) + 1
    return {"dist": dist, "warn": False, "msg": f"话题状态分布：{dist}"}


# 合法 status 字符串（见 SKILL.md §2.1 话题 · 三位一体状态流）
_VALID_STATUS = {
    "⏳ 进行中", "✅ 已关闭", "⏸️ 已搁置", "🔻 已推翻", "🗑️ 已废弃",
    "💭 讨论中", "🌱 待提炼", "📦 已封存",
    "⬜ 未开始", "✅ 已完成", "⚠️ 阻塞中",
}


def _check_status_format(topics: dict) -> dict:
    """校验 card.md 的 status 字段：必须用完整字符串（emoji+空格+中文）。"""
    bad: list[dict] = []
    for data in topics.values():
        status = data["frontmatter"].get("status")
        if status is None or not isinstance(status, str):
            continue
        if status.strip() not in _VALID_STATUS:
            bad.append({"slug": data["slug"], "status": status})
    return {
        "bad": bad,
        "warn": len(bad) > 0,
        "msg": "status 字段格式规范" if not bad else f"status 格式异常 {len(bad)} 张",
    }


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="项目健康检查。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON（给 dashboard 调用）")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    topics = load_topics(root)

    result = {
        "stream": _check_stream(root),
        "vision": _check_vision(root),
        "card_structure": _check_card_structure(topics),
        "links": _check_links(topics),
        "status_format": _check_status_format(topics),
        "status": _check_status_distribution(topics),
    }
    result["warn_count"] = sum(1 for v in result.values() if isinstance(v, dict) and v.get("warn"))

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"项目：{root}")
    print(f"告警数：{result['warn_count']}")
    print("-" * 60)
    for key in ["stream", "vision", "card_structure", "links", "status_format", "status"]:
        v = result[key]
        icon = "⚠️ " if v.get("warn") else "✅ "
        print(f"{icon}[{key}] {v.get('msg', '')}")

    # 详情
    cs = result["card_structure"]
    if cs["no_toc"]:
        print(f"  无 TOC 的卡：{', '.join(cs['no_toc'])}")
    if cs["mismatch"]:
        print(f"  TOC 不对齐：")
        for m in cs["mismatch"]:
            print(f"    - {m}")
    lk = result["links"]
    if lk["broken_parent"]:
        print(f"  parent 断链：")
        for b in lk["broken_parent"]:
            print(f"    - {b}")
    if lk["broken_link"]:
        print(f"  [[]] 断链：")
        for b in lk["broken_link"]:
            print(f"    - {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
