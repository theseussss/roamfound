# -*- coding: utf-8 -*-
"""
role_manager.py · 生成并打开 .jiacong/dashboard/role_manager.html

用法：
    python role_manager.py <项目根> [--no-open]

行为：
    - 扫描 skill 全局角色库：<skill根>/roles-library/
    - 扫描项目角色库：<项目根>/base/perspectives/
    - 构造左右两栏 context（全局 vs 项目）
    - 渲染 <skill根>/templates/role/manager.html.tmpl
    - 写 <项目根>/.jiacong/dashboard/role_manager.html
    - 默认 webbrowser.open 打开页面
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.data import (  # noqa: E402
    configure_stdout_utf8,
    ensure_project_root,
    now_datetime,
)

try:
    import frontmatter as _fm  # type: ignore
    _HAS_FM = True
except ImportError:
    _HAS_FM = False

_SKILL_ROOT = Path(__file__).parent.parent


def _parse_role_frontmatter(md_path: Path) -> dict:
    """读角色卡 frontmatter；python-frontmatter 不可用时降级仅给 id。"""
    if _HAS_FM:
        try:
            post = _fm.load(str(md_path))
            return dict(post.metadata) if post.metadata else {}
        except Exception:
            return {}
    return {}


def _scan_roles(roles_dir: Path) -> list[dict]:
    """扫描角色目录，返回角色卡列表（含 frontmatter 真实字段）。"""
    if not roles_dir.exists():
        return []
    roles: list[dict] = []
    for md in sorted(roles_dir.rglob("*.md")):
        if md.name.startswith("_"):  # 跳过 _index.md
            continue
        category = md.parent.name if md.parent != roles_dir else "other"
        fm = _parse_role_frontmatter(md)
        # H1 可能承载角色标题，若 fm 无 name 则回退用 stem
        name = fm.get("name") or fm.get("role_title") or md.stem
        verified = fm.get("verified_projects") or []
        if isinstance(verified, str):
            verified = [verified] if verified else []
        roles.append({
            "id": fm.get("id") or md.stem,
            "name": name,
            "category": fm.get("category") or category,
            "scope": fm.get("scope") or "",
            "verified_projects": verified,
            "path": str(md),
            "relative": str(md.relative_to(roles_dir)),
        })
    return roles


def _skill_roles_dir() -> Path:
    """skill 内的全局角色库（跨项目共享）"""
    return _SKILL_ROOT / "roles-library"


def main(argv: list[str] | None = None) -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description="启动角色库双向通道。")
    parser.add_argument("root", help="项目根目录")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args(argv)

    root = ensure_project_root(Path(args.root))
    tmpl_path = _SKILL_ROOT / "templates" / "role" / "manager.html.tmpl"

    global_dir = _skill_roles_dir()
    project_dir = root / "base" / "perspectives"

    context = {
        "project_name": root.name,
        "project_root": str(root),
        "global_roles_dir": str(global_dir),
        "project_roles_dir": str(project_dir),
        "global_roles": _scan_roles(global_dir),
        "project_roles": _scan_roles(project_dir),
        "generated_at": now_datetime(),
    }

    if not tmpl_path.exists():
        print(
            f"[错误] 模板不存在：{tmpl_path}\n"
            f"       已收集 context：global_roles ({len(context['global_roles'])} 张) / "
            f"project_roles ({len(context['project_roles'])} 张)",
            file=sys.stderr,
        )
        return 2

    try:
        from jinja2 import Template  # type: ignore
    except ImportError:
        print("[错误] 需要 jinja2；请 pip install jinja2", file=sys.stderr)
        return 2

    tmpl_text = tmpl_path.read_text(encoding="utf-8")
    html = Template(tmpl_text, keep_trailing_newline=True).render(**context)

    out_path = root / ".jiacong" / "dashboard" / "role_manager.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[ok] {out_path}")
    print(f"     全局角色 {len(context['global_roles'])} 张 / 项目角色 {len(context['project_roles'])} 张")

    if not args.no_open:
        try:
            webbrowser.open(out_path.as_uri())
        except Exception as e:
            print(f"[提示] 无法自动打开浏览器：{e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
