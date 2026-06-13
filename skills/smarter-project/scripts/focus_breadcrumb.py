# -*- coding: utf-8 -*-
"""
focus_breadcrumb.py · 从 focus 权威源追溯面包屑

用法：
    python focus_breadcrumb.py <项目根>

行为：
    - 优先读 <项目根>/.jiacong/focus.json
    - 兼容读 <项目根>/.claude/focus（单行，NNN 或 NNN:TMM）
    - 从 load_topics() 定位焦点话题
    - 逆向追溯 parent 链
    - 输出：004 流程优化 > 100 项目管理体系 > 112 脚本工具链
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import configure_stdout_utf8, ensure_project_root  # noqa: E402
from _lib.topics_loader import load_topics  # noqa: E402


def _read_focus_value(root: Path) -> str:
    """返回话题 focus 值；JSON 优先，旧文本兼容。"""
    focus_json = root / ".jiacong" / "focus.json"
    try:
        data = json.loads(focus_json.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            topic_id = str(data.get("topic_id") or "").strip()
            if topic_id:
                return topic_id
    except Exception:
        pass

    focus_file = root / ".claude" / "focus"
    try:
        raw = focus_file.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    for line in raw.splitlines():
        value = line.strip()
        if value:
            return value
    return ""


def compute_breadcrumb(root: Path) -> str:
    """计算面包屑（给 dashboard 复用）。"""
    raw = _read_focus_value(root)
    if not raw:
        return ""

    # 兼容旧 NNN:TMM 格式，但新 focus 只锚定话题。
    focus_main = raw.split(":", 1)[0].strip()

    topics = load_topics(root)
    by_slug = {t["slug"]: t for t in topics.values()}
    short_to_slug = {
        t["slug"].split("_", 1)[0]: t["slug"] for t in topics.values() if "_" in t["slug"]
    }

    # 定位焦点 slug
    focus_slug = None
    if focus_main in by_slug:
        focus_slug = focus_main
    elif focus_main in short_to_slug:
        focus_slug = short_to_slug[focus_main]
    else:
        return f"[焦点不存在] {raw}"

    chain: list[str] = []
    cur = focus_slug
    seen: set[str] = set()
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

    crumb = " > ".join(reversed(chain))
    return crumb


def main() -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="从 .jiacong/focus.json 追溯面包屑（旧 .claude/focus fallback）。")
    parser.add_argument("root", help="项目根目录")
    args = parser.parse_args()

    root = ensure_project_root(Path(args.root))
    crumb = compute_breadcrumb(root)
    if crumb:
        print(crumb)
        return 0
    print("[info] .jiacong/focus.json 不存在或为空（旧 .claude/focus fallback 也为空）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
