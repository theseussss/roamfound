# -*- coding: utf-8 -*-
"""
guard · card.md / scratch.md 的校验 + 确定性自动修复

合并原 structure.py 校验部分 + autofix.py 全部。
- 校验：check_card_structure / warn_only（结构一致性检查）
- 修复：fix_card / fix_scratch / fix_root_field（补齐缺失结构）

修复函数内部保留独立的 _parse_frontmatter，因其与 _rebuild_frontmatter
保序机制紧耦合（token 值比对依赖同源解析），不可替换为 data.py 的版本。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

try:
    from .data import parse_toc_entry, parse_section_heading
except ImportError:
    from data import parse_toc_entry, parse_section_heading  # type: ignore


# =========================================================================== #
# 第一部分：校验（原 structure.py 校验部分）
# =========================================================================== #

SIBLING_LIMIT = 7
UNEVEN_RATIO = 3.0


def _norm_title(value: str) -> str:
    title = re.sub(r"^\d+(?:\.\d+)*\s+", "", str(value)).strip().lower()
    title = title.strip("*")
    return title


def _ensure_toc_item(item: dict) -> dict:
    if "num" in item and "title" in item:
        return item
    return parse_toc_entry(
        str(item.get("title", "")),
        fallback_level=int(item.get("level", 1)),
        source=item.get("source", "legacy"),
    )


def _ensure_section_item(item: dict) -> dict:
    if "num" in item and "title" in item:
        return item
    return parse_section_heading(
        str(item.get("heading", "")),
        int(item.get("level", 2)),
    )


def _parent_num(num: str) -> str:
    return num.rsplit(".", 1)[0] if "." in num else ""


def check_card_structure(toc: list[dict], sections: list[dict]) -> list[dict]:
    issues: list[dict] = []

    toc_items = [_ensure_toc_item(t) for t in toc]
    section_items = [_ensure_section_item(s) for s in sections]

    if not toc_items:
        issues.append({"level": "warn", "code": "no_toc", "msg": "缺少 frontmatter toc / 📑 本卡目录"})
        return issues

    numbered_toc = [t for t in toc_items if t.get("num")]
    numbered_sections = [s for s in section_items if s.get("num")]
    strict_frontmatter = any(t.get("source") == "frontmatter" for t in toc_items)

    if strict_frontmatter and numbered_toc:
        if len(numbered_toc) != len(numbered_sections):
            issues.append({
                "level": "warn",
                "code": "count_mismatch",
                "msg": f"TOC 编号条目 {len(numbered_toc)} 条 ≠ 正文编号章节 {len(numbered_sections)} 个",
            })

        for i, (t, s) in enumerate(zip(numbered_toc, numbered_sections)):
            if t["num"] != s["num"]:
                issues.append({
                    "level": "warn",
                    "code": "num_mismatch",
                    "msg": f"第 {i + 1} 条 TOC 编号 {t['num']} ≠ 正文编号 {s['num']}",
                })
            expected_level = t["level"] + 1
            if s["level"] != expected_level:
                issues.append({
                    "level": "warn",
                    "code": "level_mismatch",
                    "msg": f"§{t['num']} 应使用 H{expected_level}，正文为 H{s['level']}",
                })
            if _norm_title(t["title"]) != _norm_title(s["title"]):
                issues.append({
                    "level": "warn",
                    "code": "text_mismatch",
                    "msg": f"§{t['num']} TOC='{t['title']}' ≠ 正文='{s['title']}'",
                })

        toc_top = [t for t in numbered_toc if t["level"] == 1]
        h2_top = [s for s in numbered_sections if s["level"] == 2]
    else:
        toc_top = [t for t in toc_items if t["level"] == 1]
        h2_top = [s for s in section_items if s["level"] == 2]
        if len(toc_top) != len(h2_top):
            issues.append({
                "level": "warn",
                "code": "count_mismatch",
                "msg": f"TOC 顶层 {len(toc_top)} 条 ≠ 正文 H2 {len(h2_top)} 个",
            })
        for i, (t, s) in enumerate(zip(toc_top, h2_top)):
            if _norm_title(t["title"]) != _norm_title(s["heading"]):
                issues.append({
                    "level": "warn",
                    "code": "text_mismatch",
                    "msg": f"第 {i + 1} 条 TOC='{t['title']}' ≠ H2='{s['heading']}'",
                })

    if len(toc_top) > SIBLING_LIMIT:
        issues.append({
            "level": "info",
            "code": "too_many_siblings",
            "msg": f"顶层章节数 {len(toc_top)} 超过阈值 {SIBLING_LIMIT}，考虑拆分或分组",
        })

    sibling_counts: dict[str, int] = {}
    for t in numbered_toc:
        sibling_counts[_parent_num(t["num"])] = sibling_counts.get(_parent_num(t["num"]), 0) + 1
    for parent, count in sibling_counts.items():
        if parent and count > SIBLING_LIMIT:
            issues.append({
                "level": "info",
                "code": "too_many_subsections",
                "msg": f"§{parent} 下子章节数 {count} 超过阈值 {SIBLING_LIMIT}，考虑拆分或分组",
            })

    h3_counts: list[int] = []
    cur: int | None = None
    for s in section_items:
        if s["level"] == 2:
            if cur is not None:
                h3_counts.append(cur)
            cur = 0
        elif s["level"] == 3 and cur is not None:
            cur += 1
    if cur is not None:
        h3_counts.append(cur)
    h3_counts = [c for c in h3_counts if c > 0]
    if len(h3_counts) >= 2:
        mn, mx = min(h3_counts), max(h3_counts)
        if mn > 0 and mx / mn >= UNEVEN_RATIO:
            issues.append({
                "level": "info",
                "code": "uneven_depth",
                "msg": f"H3 分布不均（最少 {mn} / 最多 {mx}），考虑重组",
            })

    return issues


def warn_only(issues: list[dict]) -> list[dict]:
    return [i for i in issues if i["level"] == "warn"]


# =========================================================================== #
# 第二部分：修复（原 autofix.py 全部）
# =========================================================================== #

# --------------------------------------------------------------------------- #
# 修复常量与模板
# --------------------------------------------------------------------------- #

_FIELD_TOKEN = "\x00FIELD"
_RAW_TOKEN = "\x00RAW"
_SEP = "\x00"

_META_PREFIXES = ("🔗", "💬", "🧾", "📑")

_CARD_TOC_HEAD = "## 📑 本卡目录"
_CARD_LINK_HEAD = "## 🔗 链接"
_CARD_QUOTES_HEAD = "## 💬 最佳原话"
_CARD_VERSION_HEAD = "## 🧾 版本与脚注"
_SCRATCH_DISCUSSION_HEAD = "## 💭 讨论记录"

_TOC_COMMENT_BLOCK = """## 📑 本卡目录

<!-- ⚠️ 本区由 card_write.py 自动渲染，勿直接编辑。源：frontmatter toc 字段 -->
<!-- 结构变更须用户审批：改 frontmatter toc → card_write.py --mode restructure -->"""

_SCRATCH_STATE_BLOCK = """> **状态机**：💭 讨论中 → 🌱 待提炼 → 📦 已封存（保留存档）
> **书写规范**：每段以 `[YYYY-MM-DD HH:MM]` 时间戳开头，最新追加在下方
> **迁移标记**：认知结论迁入 `card.md` 正文后，本段末尾标注 `→ card §N`
> **定位**：讨论过程即使已提炼也是**数据资产**，不删不清。card.md 为沉淀结论，scratch.md 为原始过程。"""


# --------------------------------------------------------------------------- #
# 修复内部解析（与 _rebuild_frontmatter 保序机制配对）
# --------------------------------------------------------------------------- #

def _parse_frontmatter(text: str) -> tuple[dict, str, str]:
    if not text.startswith("---"):
        return {}, "", text

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, "", text

    end = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end == -1:
        return {}, "", text

    raw = "".join(lines[1:end])
    body = "".join(lines[end + 1:])
    fm: dict = {}
    for line in raw.splitlines():
        parsed = _parse_field_line(line)
        if parsed is None:
            continue
        key, value = parsed
        fm[key] = value
    return fm, raw, body


def _parse_field_line(line: str) -> tuple[str, str] | None:
    if not line or line[0].isspace() or line.lstrip().startswith("#"):
        return None
    if ":" not in line:
        return None
    key, _, value = line.partition(":")
    key = key.strip()
    if not key:
        return None
    return key, value.strip()


def _frontmatter_order(raw: str) -> list[str]:
    order: list[str] = []
    for line in raw.splitlines():
        parsed = _parse_field_line(line)
        if parsed is None:
            order.append(_RAW_TOKEN + line)
            continue
        key, value = parsed
        order.append(_FIELD_TOKEN + _SEP + key + _SEP + value + _SEP + line)
    return order


def _rebuild_frontmatter(fm: dict, original_order: list[str]) -> str:
    lines = ["---"]
    seen: set[str] = set()

    for token in original_order:
        if token.startswith(_RAW_TOKEN):
            lines.append(token[len(_RAW_TOKEN):])
            continue

        key = token
        original_value = None
        original_line = None
        if token.startswith(_FIELD_TOKEN):
            parts = token.split(_SEP, 4)
            if len(parts) == 5:
                key = parts[2]
                original_value = parts[3]
                original_line = parts[4]

        if key not in fm:
            continue
        seen.add(key)
        if original_line is not None and str(fm.get(key, "")) == original_value:
            lines.append(original_line)
        else:
            lines.append(_format_frontmatter_line(key, fm[key]))

    for key, value in fm.items():
        if key in seen:
            continue
        lines.append(_format_frontmatter_line(key, value))

    lines.append("---")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 修复工具函数
# --------------------------------------------------------------------------- #

def _ensure_fields(fm: dict, defaults: list[tuple[str, object]]) -> list[str]:
    missing: list[str] = []
    for key, value in defaults:
        if key in fm:
            continue
        fm[key] = value
        missing.append(key)
    return missing


def _has_frontmatter_toc(fm: dict) -> bool:
    toc = fm.get("toc")
    if isinstance(toc, list):
        return bool(toc)
    if isinstance(toc, str):
        return bool(toc.strip())
    return False


def _format_frontmatter_line(key: str, value: object) -> str:
    if isinstance(value, list):
        rendered = "[]" if not value else "[" + ", ".join(str(v) for v in value) + "]"
    elif value is None:
        rendered = "null"
    else:
        rendered = str(value)
    if rendered == "":
        return f"{key}: "
    return f"{key}: {rendered}"


def _compose_text(fm: dict, original_order: list[str], body: str) -> str:
    frontmatter = _rebuild_frontmatter(fm, original_order)
    if body:
        if body.startswith("\n"):
            return frontmatter + body
        return frontmatter + "\n" + body
    return frontmatter + "\n"


def _has_heading(body: str, heading: str) -> bool:
    return any(line.strip() == heading for line in body.splitlines())


def _is_h2(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("## ") and not stripped.startswith("### ")


def _heading_text(line: str) -> str:
    return line.strip()[3:].strip()


def _card_h2_sections(body: str) -> list[str]:
    sections: list[str] = []
    for line in body.splitlines():
        if not _is_h2(line):
            continue
        heading = _heading_text(line)
        if heading.startswith(_META_PREFIXES):
            continue
        sections.append(heading)
    return sections


def _toc_title(title: str) -> str:
    text = title.strip()
    idx = 0
    while idx < len(text) and text[idx].isdigit():
        idx += 1
    if idx == 0:
        return text
    rest = text[idx:].lstrip()
    while rest.startswith((".", "．", "、", ")", "）", "·")):
        rest = rest[1:].lstrip()
    return rest or text


def _toc_entries_for_sections(sections: list[str]) -> str:
    return "\n".join(
        f"- {idx} · {_toc_title(title)}"
        for idx, title in enumerate(sections, start=1)
    )


def _insert_toc_section(body: str) -> str:
    sections = _card_h2_sections(body)
    entries = _toc_entries_for_sections(sections)
    block = _TOC_COMMENT_BLOCK
    if entries:
        block += "\n\n" + entries
    return _insert_before_first_h2(body, block)


def _insert_before_first_h2(body: str, block: str) -> str:
    lines = body.split("\n")
    for idx, line in enumerate(lines):
        if _is_h2(line):
            return _insert_lines(lines, idx, block)

    for idx, line in enumerate(lines):
        if line.strip().startswith("# ") and not line.strip().startswith("## "):
            insert_at = idx + 1
            while insert_at < len(lines) and lines[insert_at] == "":
                insert_at += 1
            return _insert_lines(lines, insert_at, block)

    return _insert_lines(lines, 0, block)


def _insert_lines(lines: list[str], index: int, block: str) -> str:
    insert = block.strip("\n").split("\n")
    before = list(lines[:index])
    after = list(lines[index:])
    if before and before[-1] != "":
        before.append("")
    if after and after[0] != "":
        insert.append("")
    return "\n".join(before + insert + after)


def _fix_toc_format(body: str) -> tuple[str, bool]:
    lines = body.split("\n")
    start = -1
    for idx, line in enumerate(lines):
        if line.strip() == _CARD_TOC_HEAD:
            start = idx
            break
    if start == -1:
        return body, False

    changed = False
    in_comment = False
    seq = 1
    for idx in range(start + 1, len(lines)):
        line = lines[idx]
        stripped = line.strip()
        if idx > start + 1 and _is_h2(line):
            break
        if "<!--" in stripped:
            in_comment = True
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue

        rewritten = _rewrite_toc_entry(line, seq)
        if rewritten is None:
            continue
        if rewritten != line:
            lines[idx] = rewritten
            changed = True
        seq += 1

    if not changed:
        return body, False
    return "\n".join(lines), True


def _rewrite_toc_entry(line: str, seq: int) -> str | None:
    indent_len = len(line) - len(line.lstrip(" "))
    indent = line[:indent_len]
    stripped = line.strip()
    content = ""

    if stripped.startswith("- "):
        content = stripped[2:].strip()
    else:
        ordered = _split_ordered_item(stripped)
        if ordered is None:
            return None
        content = ordered

    title = _strip_toc_entry_number(content)
    if not title:
        title = content
    return f"{indent}- {seq} · {title}"


def _split_ordered_item(stripped: str) -> str | None:
    idx = 0
    while idx < len(stripped) and stripped[idx].isdigit():
        idx += 1
    if idx == 0 or idx >= len(stripped):
        return None
    if stripped[idx] in (".", "．", "、", ")", "）"):
        return stripped[idx + 1:].strip()
    if stripped[idx].isspace():
        return stripped[idx:].strip()
    return None


def _strip_toc_entry_number(content: str) -> str:
    text = content.strip()
    if "·" in text:
        left, _, right = text.partition("·")
        if _digits_only(left.strip()):
            return right.strip()

    idx = 0
    while idx < len(text) and text[idx].isdigit():
        idx += 1
    if idx == 0:
        return text
    if idx < len(text) and (
        text[idx].isspace() or text[idx] in (".", "．", "、", ")", "）")
    ):
        rest = text[idx:].lstrip()
        while rest.startswith((".", "．", "、", ")", "）")):
            rest = rest[1:].lstrip()
        return rest
    return text


def _digits_only(text: str) -> bool:
    return bool(text) and all(ch.isdigit() for ch in text)


def _insert_before_meta_or_append(body: str, block: str, headings: tuple[str, ...]) -> str:
    lines = body.split("\n")
    for idx, line in enumerate(lines):
        if line.strip() in headings:
            return _insert_lines(lines, idx, block)
    return _append_block(body, block)


def _append_block(body: str, block: str) -> str:
    clean_block = block.strip("\n")
    if not body:
        return clean_block + "\n"
    if body.endswith("\n\n"):
        sep = ""
    elif body.endswith("\n"):
        sep = "\n"
    else:
        sep = "\n\n"
    return body + sep + clean_block + "\n"


def _insert_after_frontmatter_body(body: str, block: str) -> str:
    if not body:
        return block.strip("\n") + "\n"
    if body.startswith("\n"):
        return "\n" + block.strip("\n") + "\n" + body
    return block.strip("\n") + "\n\n" + body


def _insert_after_h1(body: str, block: str) -> str:
    lines = body.split("\n")
    for idx, line in enumerate(lines):
        if line.strip().startswith("# ") and not line.strip().startswith("## "):
            insert_at = idx + 1
            while insert_at < len(lines) and lines[insert_at].strip() == "":
                insert_at += 1
            return _insert_lines(lines, insert_at, block)
    return _insert_after_frontmatter_body(body, block)


def _link_block(parent_link: str) -> str:
    return f"""---

## 🔗 链接

- **父**：{parent_link}
- **子**：
- **相关**："""


def _quotes_block() -> str:
    return """---

## 💬 最佳原话

> （待填）"""


def _version_block() -> str:
    return """---

## 🧾 版本与脚注"""


def _clean_scalar(value: object) -> str:
    if isinstance(value, list):
        return "[]"
    text = "" if value is None else str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1].strip()
    return text


def _normalize_parent(value: object) -> str:
    parent = _clean_scalar(value)
    if parent.startswith("[[") and parent.endswith("]]"):
        parent = parent[2:-2]
        if "|" in parent:
            parent = parent.split("|", 1)[0]
    parent = parent.strip()
    if not parent or parent.lower() in ("null", "none"):
        return "null"
    return parent


def _find_parent_card(root: Path, parent: str) -> Path | None:
    topics_dir = root / "topics"
    direct = topics_dir / parent / "card.md"
    if direct.exists():
        return direct

    if len(parent) == 3 and parent.isdigit() and topics_dir.exists():
        prefix = parent + "_"
        for child in topics_dir.iterdir():
            if child.is_dir() and child.name.startswith(prefix):
                card = child / "card.md"
                if card.exists():
                    return card
    return None


def _extract_first_seed_root(seeds_path: Path) -> str:
    if not seeds_path.exists():
        return ""
    text = seeds_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        if "`" in stripped:
            parts = stripped.split("`")
            if len(parts) >= 3 and parts[1].strip():
                return parts[1].strip()
        value = stripped[1:].strip()
        if value:
            return value
    return ""


# --------------------------------------------------------------------------- #
# 公开修复接口
# --------------------------------------------------------------------------- #

def fix_card(path: Path, root: Path) -> list[str]:
    path = Path(path)
    root = Path(root)
    text = path.read_text(encoding="utf-8")
    fm, raw, body = _parse_frontmatter(text)
    original_order = _frontmatter_order(raw)
    fixes: list[str] = []

    missing = _ensure_fields(
        fm,
        [
            ("topic_id", path.parent.name),
            ("parent", "null"),
            ("root", ""),
            ("status", "⏳ 进行中"),
            ("created", date.today().isoformat()),
            ("updated", date.today().isoformat()),
            ("tags", []),
            ("role", ""),
            ("acceptance_criteria", []),
        ],
    )
    if missing:
        fixes.append(f"补齐 card frontmatter 字段：{', '.join(missing)}")

    if not _has_heading(body, _CARD_TOC_HEAD):
        body = _insert_toc_section(body)
        fixes.append("补齐 card 本卡目录")

    if not _has_frontmatter_toc(fm):
        new_body, changed_toc = _fix_toc_format(body)
        if changed_toc:
            body = new_body
            fixes.append("规范化 legacy card TOC 条目格式")

    if not _has_heading(body, _CARD_LINK_HEAD):
        parent = _clean_scalar(fm.get("parent", "null"))
        parent_link = "—" if parent == "null" else f"[[{parent}]]"
        body = _insert_before_meta_or_append(
            body,
            _link_block(parent_link),
            (_CARD_QUOTES_HEAD, _CARD_VERSION_HEAD),
        )
        fixes.append("补齐 card 链接区")

    if not _has_heading(body, _CARD_QUOTES_HEAD):
        body = _insert_before_meta_or_append(
            body,
            _quotes_block(),
            (_CARD_VERSION_HEAD,),
        )
        fixes.append("补齐 card 最佳原话区")

    if not _has_heading(body, _CARD_VERSION_HEAD):
        body = _append_block(body, _version_block())
        fixes.append("补齐 card 版本与脚注区")

    new_text = _compose_text(fm, original_order, body)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return fixes


def fix_scratch(path: Path, root: Path) -> list[str]:
    path = Path(path)
    root = Path(root)
    text = path.read_text(encoding="utf-8")
    fm, raw, body = _parse_frontmatter(text)
    original_order = _frontmatter_order(raw)
    fixes: list[str] = []

    missing = _ensure_fields(
        fm,
        [
            ("topic_id", path.parent.name),
            ("parent", "null"),
            ("root", ""),
            ("status", "💭 讨论中"),
            ("created", date.today().isoformat()),
        ],
    )
    if missing:
        fixes.append(f"补齐 scratch frontmatter 字段：{', '.join(missing)}")

    first_lines = body.splitlines()[:10]
    if not any(line.strip().startswith("> **状态机**") for line in first_lines):
        body = _insert_after_h1(body, _SCRATCH_STATE_BLOCK)
        fixes.append("补齐 scratch 状态机说明")

    if not _has_heading(body, _SCRATCH_DISCUSSION_HEAD):
        body = _append_block(body, "---\n\n## 💭 讨论记录")
        fixes.append("补齐 scratch 讨论记录区")

    new_text = _compose_text(fm, original_order, body)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return fixes


def fix_root_field(path: Path, root: Path) -> str | None:
    path = Path(path)
    root = Path(root)
    text = path.read_text(encoding="utf-8")
    fm, raw, body = _parse_frontmatter(text)
    if _clean_scalar(fm.get("root", "")):
        return None

    parent = _normalize_parent(fm.get("parent", "null"))
    inferred = ""
    if parent != "null":
        parent_card = _find_parent_card(root, parent)
        if parent_card is not None:
            parent_text = parent_card.read_text(encoding="utf-8")
            parent_fm, _, _ = _parse_frontmatter(parent_text)
            inferred = _clean_scalar(parent_fm.get("root", ""))
    else:
        inferred = _extract_first_seed_root(root / "topics" / "_seeds.md")

    if not inferred:
        return None

    original_order = _frontmatter_order(raw)
    fm["root"] = inferred
    new_text = _compose_text(fm, original_order, body)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return f"补齐 root 字段：{inferred}"
