"""Pure, testable rules for passive Qi from chat messages.

No I/O here — the cog calls these and then persists results.
"""
from __future__ import annotations

import time


def is_countable_message(content: str, min_length: int = 5) -> bool:
    """A message is Qi-eligible if it has enough real text."""
    if not content:
        return False
    stripped = content.strip()
    return len(stripped) >= min_length


def is_repeat(content: str, last_content: str | None, last_ts: float | None,
              now: float, window: int = 60) -> bool:
    """Spam guard: identical message within `window` seconds doesn't count."""
    if last_content is None or last_ts is None:
        return False
    return content.strip() == last_content.strip() and (now - last_ts) < window


def consume_message_quota(count: int, window_start: str | None, now: float,
                          cap: int) -> tuple[bool, int, str]:
    """Enforce the rolling hourly message cap.

    Returns (allowed, new_count, new_window_start_epoch_str).
    """
    if window_start is None or (now - float(window_start)) >= 3600.0:
        return True, 1, str(now)
    if count >= cap:
        return False, count, window_start
    return True, count + 1, window_start
