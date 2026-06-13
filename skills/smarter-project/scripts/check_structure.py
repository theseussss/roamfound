# -*- coding: utf-8 -*-
"""
check_structure.py · card 的 TOC / 正文结构校验

用法：
    python check_structure.py <项目根> [--card NNN] [--json]

检查项（见 references/review-ops.md §3）：
    1. TOC 存在性
    2. TOC 顶层条目数 vs 正文 H2 章节数（粗对齐）
    3. TOC 条目文本 vs 正文标题逐条比对（严对齐，忽略前后空白）
    4. 并列过多：同一父级下 >7 子项 → 提示拆分
    5. 层级不均：某 H2 下 H3 数量远高于其他（>3 倍）→ 提示重组

原则（见 SKILL.md 硬纪律 #2）：
    - 只报告不修改
    - AI 不擅自改结构，发现问题提示用户审批
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.guard import check_card_structure  # noqa: E402
from _lib.topics_loader import load_topics  # noqa: E402


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="card TOC / 正文结构校验。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("--card", default=None, help="只检查指定 NNN 或 NNN_简称")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    topics = load_topics(root)

    # 过滤
    filtered = topics
    if args.card:
        filtered = {}
        for k, v in topics.items():
            slug = v["slug"]
            short = slug.split("_", 1)[0] if "_" in slug else slug
            if args.card == slug or args.card == short:
                filtered[k] = v
        if not filtered:
            print(f"[错误] 未找到卡片：{args.card}", file=sys.stderr)
            return 1

    report: list[dict] = []
    total_warn = 0
    total_info = 0
    for data in filtered.values():
        issues = check_card_structure(data["toc"], data["sections"])
        if issues:
            report.append({"slug": data["slug"], "issues": issues})
        for it in issues:
            if it["level"] == "warn":
                total_warn += 1
            else:
                total_info += 1

    if args.json:
        print(json.dumps({
            "cards_checked": len(filtered),
            "cards_with_issues": len(report),
            "warn": total_warn,
            "info": total_info,
            "detail": report,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"检查卡片数：{len(filtered)}")
    print(f"有问题的卡：{len(report)}（警告 {total_warn} / 信息 {total_info}）")
    print("-" * 60)
    for r in report:
        print(f"[{r['slug']}]")
        for it in r["issues"]:
            marker = "⚠️ " if it["level"] == "warn" else "ℹ️ "
            print(f"  {marker}{it['code']}: {it['msg']}")
    if not report:
        print("[ok] 所有卡片结构通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
