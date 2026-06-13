# -*- coding: utf-8 -*-
"""
flow · 话题流转事件日志（re-export 层）

实现已迁入 journal.py（改名原因：flow 语义模糊），本模块保留公开接口不变。
"""
from __future__ import annotations

import sys

try:
    from .journal import (  # noqa: F401
        VALID_EVENTS,
        append_event,
        log_created,
        log_scratch_status,
        log_card_status,
        log_migrate,
        log_parent_change,
        log_link,
        get_events,
        summarize_by_topic,
    )
except ImportError:
    from journal import (  # type: ignore  # noqa: F401
        VALID_EVENTS,
        append_event,
        log_created,
        log_scratch_status,
        log_card_status,
        log_migrate,
        log_parent_change,
        log_link,
        get_events,
        summarize_by_topic,
    )


if __name__ == "__main__":
    from pathlib import Path
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if len(sys.argv) < 2:
        print("用法：python flow.py <项目根>")
        sys.exit(1)
    root = Path(sys.argv[1])
    events = get_events(root)
    print(f"共 {len(events)} 条事件")
    by_topic = summarize_by_topic(root)
    for topic, data in by_topic.items():
        print(f"  - {topic}：{len(data['events'])} 事件，最近 {data['last_t']}")
