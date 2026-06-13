# -*- coding: utf-8 -*-
"""
common · 脚本通用工具（re-export 层）

原始实现已迁入：
  - data.py：configure_stdout_utf8, ensure_project_root, now_date, now_datetime
  - store.py：套餐定义、模板渲染、TOC 构建

本模块保留公开接口不变，外部脚本 `from _lib.common import X` 无需改动。
"""
from __future__ import annotations

try:
    from .data import configure_stdout_utf8, ensure_project_root, now_date, now_datetime  # noqa: F401
    from .store import (  # noqa: F401
        DEFAULT_TEMPLATE_REF,
        TEMPLATE_PROFILE_SPECS,
        BASE_TOPIC_TEMPLATE_PROFILES,
        DEFAULT_ROOTS_ACADEMIC,
        DEFAULT_ROOTS_EMPIRICAL,
        BASE_TOPICS_ACADEMIC,
        BASE_TOPICS_EMPIRICAL,
        BASE_TOPICS_CODE,
        ARCHITECTURE_PACKAGES,
        parse_toc_seed,
        render_toc_context,
        render_template_context,
        load_architecture,
        render_template,
        find_templates_dir,
    )
except ImportError:
    from data import configure_stdout_utf8, ensure_project_root, now_date, now_datetime  # type: ignore  # noqa: F401
    from store import (  # type: ignore  # noqa: F401
        DEFAULT_TEMPLATE_REF,
        TEMPLATE_PROFILE_SPECS,
        BASE_TOPIC_TEMPLATE_PROFILES,
        DEFAULT_ROOTS_ACADEMIC,
        DEFAULT_ROOTS_EMPIRICAL,
        BASE_TOPICS_ACADEMIC,
        BASE_TOPICS_EMPIRICAL,
        BASE_TOPICS_CODE,
        ARCHITECTURE_PACKAGES,
        parse_toc_seed,
        render_toc_context,
        render_template_context,
        load_architecture,
        render_template,
        find_templates_dir,
    )
