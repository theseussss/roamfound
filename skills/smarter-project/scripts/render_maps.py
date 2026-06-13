# -*- coding: utf-8 -*-
"""
render_maps.py · 从 card.md 单元生成地图辅助视图

用法：
    python render_maps.py <项目根> [--card NNN]

输出：
    <项目根>/.claude/maps/<topic-slug>.md

说明：
    - 只生成辅助阅读层，不替代 card.md / template.md
    - 当前支持模块节点、关系边、视觉锚点三类结构化单元
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.topics_loader import load_topics  # noqa: E402

_MAP_UNIT_KINDS: dict[str, str] = {
    "模块节点": "module_node",
    "关系边": "relation_edge",
    "视觉锚点": "visual_anchor",
}
_HEADING_RE = re.compile(
    r"^###\s+(" + "|".join(re.escape(k) for k in _MAP_UNIT_KINDS) + r")：(.+?)\s*$",
    re.MULTILINE,
)
_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$")


def _section_body(text: str, start: int) -> str:
    next_heading = re.search(r"^###\s+", text[start + 1:], re.MULTILINE)
    if not next_heading:
        return text[start:]
    return text[start:start + 1 + next_heading.start()]


def _table_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        key = m.group(1).strip()
        value = m.group(2).strip()
        if key in {"字段", ":---"} or key.startswith(":"):
            continue
        fields[key] = value
    return fields


def _parse_map_units(card_path: Path) -> dict[str, list[dict]]:
    text = card_path.read_text(encoding="utf-8")
    result: dict[str, list[dict]] = {v: [] for v in _MAP_UNIT_KINDS.values()}
    for m in _HEADING_RE.finditer(text):
        kind = m.group(1)
        title = m.group(2).strip()
        block = _section_body(text, m.start())
        fields = _table_fields(block)
        key = _MAP_UNIT_KINDS.get(kind)
        if key:
            result[key].append({"title": title, "fields": fields})
    return result


def _safe_mermaid_id(name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_一-鿿]+", "_", name).strip("_")
    return safe or "node"


def _render_mermaid(units: dict[str, list[dict]]) -> str:
    nodes = units["module_node"]
    edges = units["relation_edge"]
    if not nodes and not edges:
        return ""
    lines = ["graph LR"]
    for node in nodes:
        nid = _safe_mermaid_id(node["title"])
        label = node["title"].replace('"', "'")
        lines.append(f'  {nid}["{label}"]')
    for edge in edges:
        title = edge["title"]
        if "→" not in title:
            continue
        left, _, right = title.partition("→")
        left_id = _safe_mermaid_id(left.strip())
        right_id = _safe_mermaid_id(right.strip())
        relation = edge["fields"].get("关系类型", "关系").replace('"', "'")
        lines.append(f'  {left_id} -->|"{relation}"| {right_id}')
    return "\n".join(lines)


def _render_units_table(title: str, rows: list[dict], preferred: list[str]) -> list[str]:
    if not rows:
        return []
    lines = [f"## {title}", "", "| 名称 | " + " | ".join(preferred) + " |", "|:---" + "|:---" * len(preferred) + "|"]
    for row in rows:
        values = [row["title"]]
        values.extend(row["fields"].get(field, "") for field in preferred)
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    return lines


_MAP_UNIT_PREFERRED_FIELDS: dict[str, tuple[str, list[str]]] = {
    "module_node": ("模块节点", ["原子职责", "入口", "输出", "依赖", "被谁使用", "变更影响"]),
    "relation_edge": ("关系边", ["关系类型", "触发条件", "传递对象", "风险"]),
    "visual_anchor": ("视觉锚点", ["用户看到什么", "状态有哪些", "由什么控制", "落在哪里", "交互手感", "易错点"]),
}


def _render_map_doc(slug: str, units: dict[str, list[dict]]) -> str:
    lines = [
        f"# 地图辅助视图 · {slug}",
        "",
        "> 本文件由 `render_maps.py` 生成，只作阅读层；源数据仍以话题 `card.md` 和 `template.md` 为准。",
        "",
    ]
    mermaid = _render_mermaid(units)
    if mermaid:
        lines.extend(["## Mermaid", "", "```mermaid", mermaid, "```", ""])
    for key, (title, preferred) in _MAP_UNIT_PREFERRED_FIELDS.items():
        lines.extend(_render_units_table(title, units.get(key, []), preferred))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="生成地图辅助视图。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("--card", default=None, help="只渲染指定 NNN 或 NNN_简称")
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

    out_dir = root / ".claude" / "maps"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for data in topics.values():
        card_path = Path(data["path"])
        units = _parse_map_units(card_path)
        if not any(units.values()):
            continue
        out_path = out_dir / f"{data['slug']}.md"
        out_path.write_text(_render_map_doc(data["slug"], units), encoding="utf-8")
        print(f"[write] {out_path}")
        written += 1
    if written == 0:
        print("[ok] 未发现可渲染的地图单元")
    else:
        print(f"[ok] 已生成 {written} 个地图辅助视图")
    return 0


if __name__ == "__main__":
    sys.exit(main())
