# -*- coding: utf-8 -*-
"""
structure.py · card.md TOC / 正文结构校验公共逻辑（re-export 层）

实现已迁入：
    - 解析函数 → data.py（parse_toc_entry, parse_card_body 等）
    - 校验函数 → guard.py（check_card_structure, warn_only）
本模块保留公开接口不变。
"""
from __future__ import annotations

try:
    from .data import (  # noqa: F401
        parse_toc_entry,
        parse_toc_list,
        parse_section_heading,
        parse_card_body,
        parse_card_text,
        _TOC_SECTION_RE,
        _SECTION_RE,
        _TOC_ITEM_RE,
        _NUM_PREFIX_RE,
        _TOC_ENTRY_RE,
        _META_HEADING_PREFIXES,
    )
    from .guard import (  # noqa: F401
        check_card_structure,
        warn_only,
        SIBLING_LIMIT,
        UNEVEN_RATIO,
    )
except ImportError:
    from data import (  # type: ignore  # noqa: F401
        parse_toc_entry,
        parse_toc_list,
        parse_section_heading,
        parse_card_body,
        parse_card_text,
        _TOC_SECTION_RE,
        _SECTION_RE,
        _TOC_ITEM_RE,
        _NUM_PREFIX_RE,
        _TOC_ENTRY_RE,
        _META_HEADING_PREFIXES,
    )
    from guard import (  # type: ignore  # noqa: F401
        check_card_structure,
        warn_only,
        SIBLING_LIMIT,
        UNEVEN_RATIO,
    )
