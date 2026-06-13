# -*- coding: utf-8 -*-
"""
journal · 话题流转事件日志（append-only）

原 flow.py，改名原因：flow 在项目中还指"工作流"，journal 明确是"事件日志"。

事件日志位置：<项目根>/.claude/flow-log.jsonl

每行一条事件，JSON 格式。最小事件集（6 类）：
    - created         话题建立
    - scratch_status  💭/🌱/📦 流转
    - migrate         内容迁入 card §N
    - card_status     ⏳/✅/⏸️/🔻/🗑️ 流转
    - parent_change   parent 字段变更
    - link            新增 [[NNN]] 引用

写入纪律：
    - 只记录显式信号（字段变更、标记出现），不做语义推断
    - 所有字段都能回溯到 md 的实际变更
    - append-only，从不修改历史行
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


VALID_EVENTS = {
    "created",
    "scratch_status",
    "migrate",
    "card_status",
    "parent_change",
    "link",
}


def _log_path(root: Path) -> Path:
    return root / ".claude" / "flow-log.jsonl"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _validate(event: dict) -> None:
    for k in ("t", "topic", "event"):
        if k not in event:
            raise ValueError(f"flow event 缺必要字段：{k}")
    if event["event"] not in VALID_EVENTS:
        raise ValueError(
            f"未知事件类型：{event['event']}；允许：{sorted(VALID_EVENTS)}"
        )


def append_event(root: Path, event: dict) -> None:
    """追加一条事件；event 必含 topic + event，t 可省略自动填。"""
    event = dict(event)
    event.setdefault("t", _now_iso())
    _validate(event)

    log = _log_path(root)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# 便捷包装（六种事件类型各一个）
# --------------------------------------------------------------------------- #


def log_created(root: Path, topic: str, source: str = "manual") -> None:
    append_event(root, {"topic": topic, "event": "created", "source": source})


def log_scratch_status(
    root: Path, topic: str, from_: str, to: str, source: str = "manual"
) -> None:
    append_event(root, {
        "topic": topic, "event": "scratch_status",
        "from": from_, "to": to, "source": source,
    })


def log_card_status(
    root: Path, topic: str, from_: str, to: str, source: str = "manual"
) -> None:
    append_event(root, {
        "topic": topic, "event": "card_status",
        "from": from_, "to": to, "source": source,
    })


def log_migrate(
    root: Path, topic: str, to_section: str, snippet: str = "",
    source: str = "manual"
) -> None:
    append_event(root, {
        "topic": topic, "event": "migrate",
        "to": to_section, "snippet": snippet, "source": source,
    })


def log_parent_change(
    root: Path, topic: str, from_: str, to: str, source: str = "manual"
) -> None:
    append_event(root, {
        "topic": topic, "event": "parent_change",
        "from": from_, "to": to, "source": source,
    })


def log_link(
    root: Path, topic: str, to_slug: str, source: str = "manual"
) -> None:
    append_event(root, {
        "topic": topic, "event": "link",
        "to": to_slug, "source": source,
    })


# --------------------------------------------------------------------------- #
# 读取
# --------------------------------------------------------------------------- #


def get_events(
    root: Path,
    topic: str | None = None,
    since: datetime | None = None,
    event_type: str | None = None,
) -> list[dict]:
    """读 flow-log，可按 topic/since/event_type 过滤。"""
    log = _log_path(root)
    if not log.exists():
        return []
    events: list[dict] = []
    with open(log, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if topic and ev.get("topic") != topic:
                continue
            if event_type and ev.get("event") != event_type:
                continue
            if since:
                try:
                    t = datetime.fromisoformat(ev["t"])
                    if t < since:
                        continue
                except (KeyError, ValueError):
                    continue
            events.append(ev)
    return events


def summarize_by_topic(root: Path) -> dict[str, dict]:
    """按 topic 聚合：事件列表 + 最近时间戳。"""
    result: dict[str, dict] = {}
    for ev in get_events(root):
        topic = ev.get("topic")
        if not topic:
            continue
        if topic not in result:
            result[topic] = {"events": [], "last_t": None}
        result[topic]["events"].append(ev)
        result[topic]["last_t"] = ev.get("t")
    return result


# --------------------------------------------------------------------------- #
# CLI 自检
# --------------------------------------------------------------------------- #


def _main() -> int:
    """独立运行时：`python journal.py <项目根>` 打印摘要。"""
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if len(sys.argv) < 2:
        print("用法：python journal.py <项目根>")
        return 1
    root = Path(sys.argv[1])
    events = get_events(root)
    print(f"共 {len(events)} 条事件")
    by_topic = summarize_by_topic(root)
    for topic, data in by_topic.items():
        print(f"  - {topic}：{len(data['events'])} 事件，最近 {data['last_t']}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
