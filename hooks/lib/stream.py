# -*- coding: utf-8 -*-
"""Project stream freshness checks."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from .messages import msg


def stream_messages(project_root: Path, skill_dir: Path) -> list[str]:
    stream_path = project_root / "logs" / "stream.md"
    if not stream_path.is_file():
        return [
            msg(
                "stream.missing",
                init_script=skill_dir / "scripts" / "init_project.py",
                project_root=project_root,
            )
        ]

    now = datetime.now()
    last_entry = last_stream_entry(stream_path, now)
    if last_entry is None:
        return []
    if now - last_entry > timedelta(hours=24):
        return [msg("stream.stale", last_entry=f"{last_entry:%Y-%m-%d %H:%M}")]
    return []


def stream_line_count(project_root: Path) -> int:
    try:
        return len((project_root / "logs" / "stream.md").read_text(encoding="utf-8").splitlines())
    except Exception:
        return 0


def last_stream_entry(stream_path: Path, now: datetime) -> datetime | None:
    try:
        lines = stream_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        try:
            for match in reversed(list(re.finditer(r"\[([^\]]+)\]", line))):
                parsed = parse_bracketed_timestamp(match.group(1), now)
                if parsed is not None:
                    return parsed
        except Exception:
            continue
    return None


def parse_bracketed_timestamp(text: str, now: datetime) -> datetime | None:
    patterns = [
        re.compile(
            r"(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})"
            r"(?:[ T]+(?P<hour>\d{1,2})(?::?(?P<minute>\d{2}))?)?"
        ),
        re.compile(
            r"(?P<month>\d{1,2})[-/](?P<day>\d{1,2})"
            r"(?:[ T]+(?P<hour>\d{1,2})(?::?(?P<minute>\d{2}))?)?"
        ),
    ]

    for pattern in patterns:
        match = pattern.search(text.strip())
        if not match:
            continue
        parts = match.groupdict()
        year_text = parts.get("year")
        return build_datetime(
            now,
            int(year_text) if year_text else None,
            parts["month"],
            parts["day"],
            parts.get("hour"),
            parts.get("minute"),
        )
    return None


def build_datetime(
    now: datetime,
    year: int | None,
    month: str,
    day: str,
    hour: str | None = None,
    minute: str | None = None,
) -> datetime | None:
    try:
        parsed_year = year if year is not None else now.year
        parsed_hour = int(hour) if hour is not None else 0
        parsed_minute = int(minute) if minute is not None else 0
        parsed = datetime(parsed_year, int(month), int(day), parsed_hour, parsed_minute)
        if year is None and parsed > now + timedelta(days=1):
            parsed = parsed.replace(year=parsed.year - 1)
        return parsed
    except Exception:
        return None
