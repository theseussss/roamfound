# -*- coding: utf-8 -*-
"""
data · 共享数据访问层

统一 frontmatter 解析（消除 autofix / topics_loader / structure / flow_hook 四处重复），
提供话题数据读取和项目根验证等公共基础设施。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import frontmatter as _fm  # type: ignore
    _HAS_FM = True
except ImportError:
    _HAS_FM = False


# --------------------------------------------------------------------------- #
# 通用工具（原 common.py）
# --------------------------------------------------------------------------- #

def configure_stdout_utf8() -> None:
    """Windows Git Bash/cmd 默认 codepage 不支持 UTF-8，强制 stdout 使用 UTF-8。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def ensure_project_root(root: Path) -> Path:
    """验证项目根合法（必须已存在）。返回绝对路径。"""
    root = Path(root).resolve()
    if not root.exists():
        raise SystemExit(f"[错误] 项目根不存在：{root}")
    if not root.is_dir():
        raise SystemExit(f"[错误] 项目根不是目录：{root}")
    return root


def now_date() -> str:
    """返回 YYYY-MM-DD。"""
    return datetime.now().strftime("%Y-%m-%d")


def now_datetime() -> str:
    """返回 YYYY-MM-DD HH:MM。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------- #
# 统一 frontmatter 解析
# --------------------------------------------------------------------------- #

_FM_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def parse_frontmatter(text: str) -> tuple[dict, str, str]:
    """
    统一 frontmatter 解析入口。

    返回 (fm_dict, raw_frontmatter, body)：
    - fm_dict: 字段字典（一级标量 + 列表字段）
    - raw_frontmatter: --- 之间的原始文本（autofix 保序重建用）
    - body: frontmatter 之后的正文
    """
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

    if _HAS_FM:
        try:
            post = _fm.loads(text)
            return dict(post.metadata), raw, post.content
        except Exception:
            pass

    fm: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if current_list_key and line[:1].isspace():
            if stripped.startswith("- "):
                value = stripped[2:].strip().strip('"').strip("'")
                fm[current_list_key].append(value)
            continue
        current_list_key = None
        m = _FM_KEY_RE.match(stripped)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value:
                fm[key] = value.strip('"').strip("'")
            else:
                fm[key] = []
                current_list_key = key
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        fm[key] = value

    return fm, raw, body


def parse_frontmatter_simple(text: str) -> tuple[dict, str]:
    """兼容接口：只返回 (fm_dict, body)。"""
    fm, _, body = parse_frontmatter(text)
    return fm, body


# --------------------------------------------------------------------------- #
# card 结构解析（原 structure.py 解析部分）
# --------------------------------------------------------------------------- #

_TOC_SECTION_RE = re.compile(r"^##\s*📑\s*本卡目录\s*$")
_SECTION_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
_TOC_ITEM_RE = re.compile(r"^(\s*)-\s+(.+?)\s*$")
_NUM_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+?)\s*$")
_TOC_ENTRY_RE = re.compile(
    r'^"?(\d+(?:\.\d+)*)\s*(?:[·．]\s*|\s+)(.+?)(?:\s*(?:\||—)\s*(.+?))?"?$'
)

_META_HEADING_PREFIXES = ("🔗", "💬", "🧾", "📑")


def _clean_value(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _clean_intent(value: str | None) -> str:
    if not value:
        return ""
    return _clean_value(value).strip("*").strip()


def _clean_title(value: str) -> str:
    title = re.sub(r"\s*—\s*\*.*?\*\s*$", "", value).strip()
    title = title.split("|", 1)[0].strip()
    return _clean_value(title)


def parse_toc_entry(entry: str, fallback_level: int = 1, source: str = "frontmatter") -> dict:
    raw = _clean_value(str(entry))
    m = _TOC_ENTRY_RE.match(raw)
    if not m:
        return {
            "level": fallback_level,
            "num": "",
            "title": _clean_title(raw),
            "intent": "",
            "raw": raw,
            "source": source,
        }
    num = m.group(1)
    return {
        "level": num.count(".") + 1,
        "num": num,
        "title": _clean_title(m.group(2)),
        "intent": _clean_intent(m.group(3)),
        "raw": raw,
        "source": source,
    }


def parse_toc_list(toc_raw: list[Any], source: str = "frontmatter") -> list[dict]:
    return [parse_toc_entry(str(item), source=source) for item in toc_raw]


def parse_section_heading(heading: str, markdown_level: int) -> dict:
    m = _NUM_PREFIX_RE.match(heading.strip())
    if not m:
        return {
            "level": markdown_level,
            "toc_level": max(markdown_level - 1, 1),
            "num": "",
            "title": heading.strip(),
            "heading": heading.strip(),
        }
    num = m.group(1)
    return {
        "level": markdown_level,
        "toc_level": num.count(".") + 1,
        "num": num,
        "title": m.group(2).strip(),
        "heading": heading.strip(),
    }


def _frontmatter_toc_lines(frontmatter: dict | None) -> list[str]:
    if not frontmatter:
        return []
    raw = frontmatter.get("toc")
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        lines: list[str] = []
        for ln in raw.splitlines():
            stripped = ln.strip()
            if stripped.startswith("- "):
                lines.append(stripped[2:].strip())
            elif stripped:
                lines.append(stripped)
        return lines
    return []


def _parse_body_toc(body: str) -> list[dict]:
    toc: list[dict] = []
    in_toc = False
    for ln in body.split("\n"):
        stripped = ln.rstrip()
        sec_m = _SECTION_RE.match(stripped)
        if sec_m:
            if _TOC_SECTION_RE.match(stripped):
                in_toc = True
                continue
            in_toc = False
        if in_toc:
            item_m = _TOC_ITEM_RE.match(stripped)
            if item_m:
                indent = len(item_m.group(1))
                toc.append(parse_toc_entry(
                    item_m.group(2).strip(),
                    fallback_level=indent // 2 + 1,
                    source="body",
                ))
    return toc


def _parse_sections(body: str) -> list[dict]:
    sections: list[dict] = []
    for ln in body.split("\n"):
        stripped = ln.rstrip()
        sec_m = _SECTION_RE.match(stripped)
        if not sec_m:
            continue
        level = len(sec_m.group(1))
        heading = sec_m.group(2).strip()
        if heading.startswith(_META_HEADING_PREFIXES):
            continue
        sections.append(parse_section_heading(heading, level))
    return sections


def parse_card_body(body: str, frontmatter: dict | None = None) -> tuple[list[dict], list[dict]]:
    toc_raw = _frontmatter_toc_lines(frontmatter)
    toc = parse_toc_list(toc_raw) if toc_raw else _parse_body_toc(body)
    sections = _parse_sections(body)
    return toc, sections


def parse_card_text(text: str) -> tuple[list[dict], list[dict]]:
    fm, body = parse_frontmatter_simple(text)
    return parse_card_body(body, fm)


# --------------------------------------------------------------------------- #
# 话题数据读取（原 topics_loader.py）
# --------------------------------------------------------------------------- #

_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


def _anchor_of(heading: str) -> str:
    """把标题转成 markdown 锚点。"""
    anchor = heading.strip().lower()
    anchor = re.sub(r"\s+", "-", anchor)
    anchor = re.sub(r"[^\w\-一-鿿]", "", anchor)
    return anchor


def parse_md(card_path: Path) -> dict[str, Any]:
    """
    解析一张 card.md，返回结构化数据。

    返回字段：frontmatter, toc, sections, links, path, slug
    """
    with open(card_path, "r", encoding="utf-8") as f:
        text = f.read()

    fm, _raw, body = parse_frontmatter(text)

    toc, sections = parse_card_body(body, fm)
    for section in sections:
        section["anchor"] = _anchor_of(section["heading"])

    body_no_comment = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    links = _LINK_RE.findall(body_no_comment)

    slug = card_path.parent.name
    return {
        "frontmatter": fm,
        "toc": toc,
        "sections": sections,
        "links": links,
        "path": str(card_path),
        "slug": slug,
    }


def find_cards(topics_dir: Path) -> list[Path]:
    """返回 topics/ 下所有 card.md 路径。"""
    if not topics_dir.exists():
        return []
    return sorted(topics_dir.glob("*/card.md"))


# --------------------------------------------------------------------------- #
# Cache I/O
# --------------------------------------------------------------------------- #

def _cache_path(root: Path) -> Path:
    return root / ".claude" / ".cache" / "topics-cache.json"


def _json_default(obj: Any) -> str:
    import datetime as _dt
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def load_cache(cache_path: Path) -> dict[str, Any]:
    """加载缓存；文件不存在/损坏则返回空 dict。"""
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    """保存缓存，确保父目录存在。"""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, default=_json_default)


# --------------------------------------------------------------------------- #
# 公开接口
# --------------------------------------------------------------------------- #

def load_topics(root: Path) -> dict[str, dict]:
    """
    读取即同步：每次调用都对比 mtime，永不读到过期数据。
    返回字典，key = card 绝对路径字符串，value = parse_md 结果（含 mtime）。
    """
    root = Path(root).resolve()
    topics_dir = root / "topics"
    cp = _cache_path(root)

    cache = load_cache(cp)
    cards = find_cards(topics_dir)
    alive_keys: set[str] = set()

    for card in cards:
        key = str(card)
        alive_keys.add(key)
        try:
            mtime = os.path.getmtime(card)
        except OSError:
            continue
        if cache.get(key, {}).get("mtime") != mtime:
            parsed = parse_md(card)
            parsed["mtime"] = mtime
            cache[key] = parsed

    for key in list(cache.keys()):
        if key not in alive_keys:
            cache.pop(key, None)

    save_cache(cp, cache)
    return cache


def load_topics_by_slug(root: Path) -> dict[str, dict]:
    """便捷封装：按 slug（NNN_简称）索引。"""
    topics = load_topics(root)
    return {t["slug"]: t for t in topics.values()}
