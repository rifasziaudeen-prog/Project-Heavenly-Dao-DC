"""Tests for passive-Qi message rules (core/passive_logic.py)."""
from core import passive_logic


def test_minimum_length():
    assert passive_logic.is_countable_message("hello world") is True
    assert passive_logic.is_countable_message("hi") is False
    assert passive_logic.is_countable_message("   ") is False
    assert passive_logic.is_countable_message("") is False


def test_repeat_detection_within_window():
    t0 = 1000.0
    assert passive_logic.is_repeat("abc", "abc", t0, t0 + 10) is True
    assert passive_logic.is_repeat("abc", "abc", t0, t0 + 120) is False
    assert passive_logic.is_repeat("abc", "abd", t0, t0 + 10) is False
    assert passive_logic.is_repeat("abc", None, None, t0 + 10) is False


def test_message_quota_respects_cap():
    allowed, count, win = passive_logic.consume_message_quota(0, None, 1000.0, cap=15)
    assert allowed is True and count == 1 and win == "1000.0"
    allowed, count, _ = passive_logic.consume_message_quota(15, "1000.0", 1000.0, cap=15)
    assert allowed is False and count == 15
    allowed, count, _ = passive_logic.consume_message_quota(14, "1000.0", 1000.0, cap=15)
    assert allowed is True and count == 15


def test_message_quota_window_rolls():
    allowed, count, win = passive_logic.consume_message_quota(
        15, "1000.0", 1000.0 + 3601, cap=15
    )
    assert allowed is True and count == 1
    assert float(win) == 1000.0 + 3601
