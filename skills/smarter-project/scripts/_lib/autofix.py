# -*- coding: utf-8 -*-
"""
autofix · card.md / scratch.md 的确定性自动修复器（re-export 层）

实现已迁入 guard.py，本模块保留公开接口不变。
"""
from __future__ import annotations

try:
    from .guard import fix_card, fix_scratch, fix_root_field  # noqa: F401
except ImportError:
    from guard import fix_card, fix_scratch, fix_root_field  # type: ignore  # noqa: F401
