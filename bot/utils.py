"""Shared presentation helpers for embeds and formatting."""
from __future__ import annotations

import datetime
import json

from core import math as gm

# Theme (spec: Righteous gold/cyan, Demonic crimson, Immortal purple)
GOLD = 0xFFD700
CYAN = 0x00FFFF
CRIMSON = 0xDC143C
PURPLE = 0x8A2BE2
OBSIDIAN = 0x1A1A1A


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def now_str() -> str:
    """SQLite-friendly UTC timestamp: 'YYYY-MM-DD HH:MM:SS'."""
    return now_utc().strftime("%Y-%m-%d %H:%M:%S")


def future_str(hours: int = 0, minutes: int = 0) -> str:
    """SQLite-friendly UTC timestamp `hours`/`minutes` from now."""
    return (now_utc() + datetime.timedelta(hours=hours, minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def parse_db_time(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return None


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def progress_bar(current: int | float, total: int | float, width: int = 16) -> str:
    if total <= 0:
        return "▱" * width
    filled = int(round(width * max(0.0, min(1.0, current / total))))
    return "▰" * filled + "▱" * (width - filled)


def format_qi(value: int, lang: str = "bilingual") -> str:
    if lang == "english":
        return f"{value:,} Qi"
    return f"{value:,} 灵力"


def format_title(title: str, lang: str = "bilingual") -> str:
    if lang == "english" and " · " in title:
        return title.split(" · ")[0]
    return title


def parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def add_json_title(raw: str | None, title: str) -> str:
    titles = parse_json_list(raw)
    if title not in titles:
        titles.append(title)
    return json.dumps(titles)


def realm_summary(tier: int, sub_stage: int, lang: str = "bilingual") -> str:
    return gm.realm_label(tier, sub_stage, lang)
