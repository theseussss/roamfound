# -*- coding: utf-8 -*-
"""
check_units.py · template.md 单元模板校验

用法：
    python check_units.py <项目根> [--card NNN] [--json]

检查项：
    1. base_topic 是否存在 template.md
    2. template.md 是否含 unit 块
    3. unit 是否声明 key / section / name
    4. unit section 是否存在于 card.md frontmatter toc
    5. unit 标题是否重复
    6. unit 表格是否包含字段/内容两列
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.topics_loader import load_topics  # noqa: E402

_UNIT_BLOCK_RE = re.compile(
    r"<!--\s*unit:(?P<key>[^\s]+)\s+section:(?P<section>[^\s]*)\s+name:(?P<name>.*?)\s*-->\n"
    r"(?P<body>.*?)\n<!--\s*/unit\s*-->",
    re.DOTALL,
)
_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def _load_units(template_path: Path) -> list[dict]:
    if not template_path.exists():
        return []
    text = template_path.read_text(encoding="utf-8")
    units: list[dict] = []
    for m in _UNIT_BLOCK_RE.finditer(text):
        body = m.group("body").strip()
        heading_match = _HEADING_RE.search(body)
        units.append({
            "key": m.group("key").strip(),
            "section": m.group("section").strip(),
            "name": m.group("name").strip(),
            "heading": heading_match.group(1).strip() if heading_match else "",
            "body": body,
        })
    return units


def _has_field_table(body: str) -> bool:
    return "| 字段 | 内容 |" in body and "|:---|:---|" in body


def _check_topic(root: Path, data: dict) -> list[dict]:
    slug = data["slug"]
    topic_dir = root / "topics" / slug
    template_path = topic_dir / "template.md"
    issues: list[dict] = []
    fm = data.get("frontmatter", {}) or {}
    is_base = bool(fm.get("base_topic"))

    if is_base and not template_path.exists():
        issues.append({"level": "warn", "code": "missing_template", "msg": "基础话题缺少 template.md 第四组件"})
        return issues
    if not template_path.exists():
        return issues

    units = _load_units(template_path)
    if not units:
        issues.append({"level": "warn", "code": "no_units", "msg": "template.md 未定义任何 unit 块"})
        return issues

    toc_nums = {entry.get("num") for entry in data.get("toc", [])}
    seen_keys: set[str] = set()
    seen_headings: set[str] = set()
    for unit in units:
        label = unit["key"] or unit["name"] or "（未命名）"
        if not unit["key"]:
            issues.append({"level": "warn", "code": "unit_missing_key", "msg": f"unit 缺少 key：{label}"})
        if unit["key"] in seen_keys:
            issues.append({"level": "warn", "code": "unit_duplicate_key", "msg": f"unit key 重复：{unit['key']}"})
        seen_keys.add(unit["key"])

        if not unit["section"]:
            issues.append({"level": "warn", "code": "unit_missing_section", "msg": f"unit 未声明 section：{label}"})
        elif unit["section"] not in toc_nums:
            issues.append({"level": "warn", "code": "unit_bad_section", "msg": f"unit {label} 指向不存在的 section：{unit['section']}"})

        if not unit["name"]:
            issues.append({"level": "info", "code": "unit_missing_name", "msg": f"unit 缺少 name：{label}"})
        if not unit["heading"]:
            issues.append({"level": "warn", "code": "unit_missing_heading", "msg": f"unit 缺少三级标题：{label}"})
        elif unit["heading"] in seen_headings:
            issues.append({"level": "warn", "code": "unit_duplicate_heading", "msg": f"unit 标题重复：{unit['heading']}"})
        seen_headings.add(unit["heading"])

        if not _has_field_table(unit["body"]):
            issues.append({"level": "info", "code": "unit_no_field_table", "msg": f"unit 未使用字段/内容表格：{label}"})

    return issues


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="template.md 单元模板校验。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("--card", default=None, help="只检查指定 NNN 或 NNN_简称")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    topics = load_topics(root)
    if args.card:
        topics = {
            k: v for k, v in topics.items()
            if args.card == v["slug"] or args.card == v["slug"].split("_", 1)[0]
        }
        if not topics:
            print(f"[错误] 未找到卡片：{args.card}", file=sys.stderr)
            return 1

    report: list[dict] = []
    total_warn = 0
    total_info = 0
    for data in topics.values():
        issues = _check_topic(root, data)
        if issues:
            report.append({"slug": data["slug"], "issues": issues})
        for it in issues:
            if it["level"] == "warn":
                total_warn += 1
            else:
                total_info += 1

    if args.json:
        print(json.dumps({
            "cards_checked": len(topics),
            "cards_with_issues": len(report),
            "warn": total_warn,
            "info": total_info,
            "detail": report,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"检查话题数：{len(topics)}")
    print(f"有问题的话题：{len(report)}（警告 {total_warn} / 信息 {total_info}）")
    print("-" * 60)
    for r in report:
        print(f"[{r['slug']}]")
        for it in r["issues"]:
            marker = "⚠️ " if it["level"] == "warn" else "ℹ️ "
            print(f"  {marker}{it['code']}: {it['msg']}")
    if not report:
        print("[ok] 所有 template.md 单元通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
