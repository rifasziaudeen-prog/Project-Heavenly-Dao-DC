"""Tests for the sect engine (core/sects.py)."""
from core import sects


# ---------------------------------------------------------------------------
# Rank helpers
# ---------------------------------------------------------------------------

def test_rank_index():
    assert sects.rank_index("Outer Disciple") == 0
    assert sects.rank_index("Elder") == 3
    assert sects.rank_index("Patriarch") == 4
    # Case-insensitive
    assert sects.rank_index("patriarch") == 4
    # Unknown rank defaults to lowest
    assert sects.rank_index("Nonexistent") == 0


def test_rank_navigation():
    assert sects.next_rank(0) == 1
    assert sects.next_rank(3) == 4
    assert sects.next_rank(4) is None  # already top
    assert sects.prev_rank(4) == 3
    assert sects.prev_rank(1) == 0
    assert sects.prev_rank(0) is None  # already bottom


# ---------------------------------------------------------------------------
# Array upgrade cost (exponential)
# ---------------------------------------------------------------------------

def test_array_upgrade_cost():
    assert sects.array_upgrade_cost(1) == 500
    assert sects.array_upgrade_cost(2) == 750       # int(500 * 1.5^1)
    assert sects.array_upgrade_cost(3) == 1125      # int(500 * 1.5^2)
    assert sects.array_upgrade_cost(6) == 3796       # int(500 * 1.5^5)


def test_array_bonus_pct():
    assert sects.array_bonus_pct(0) == 0.0
    assert sects.array_bonus_pct(1) == 8.0
    assert sects.array_bonus_pct(6) == 48.0
    assert sects.array_bonus_pct(7) == 50.0  # capped at ARRAY_BONUS_CAP


# ---------------------------------------------------------------------------
# Validation: creation
# ---------------------------------------------------------------------------

def test_validate_creation_tier_gate():
    ok, _ = sects.validate_sect_creation("Sword Valley", 1)
    assert ok is False
    ok, _ = sects.validate_sect_creation("Sword Valley", 2)
    assert ok is False
    ok, _ = sects.validate_sect_creation("Sword Valley", 3)
    assert ok is True
    ok, _ = sects.validate_sect_creation("Sword Valley", 9)
    assert ok is True


def test_validate_creation_name_length():
    ok, _ = sects.validate_sect_creation("A", 3)
    assert ok is False  # too short
    ok, _ = sects.validate_sect_creation("X" * 41, 3)
    assert ok is False  # too long
    ok, _ = sects.validate_sect_creation("Heavenly Sword", 3)
    assert ok is True


# ---------------------------------------------------------------------------
# Validation: join
# ---------------------------------------------------------------------------

def test_validate_join_already_in_sect():
    ok, reason = sects.validate_join(has_sect=True, max_members=20, current_count=5)
    assert ok is False and "already belong" in reason


def test_validate_join_sect_full():
    ok, reason = sects.validate_join(has_sect=False, max_members=20, current_count=20)
    assert ok is False and "capacity" in reason


def test_validate_join_valid():
    ok, _ = sects.validate_join(has_sect=False, max_members=20, current_count=5)
    assert ok is True


# ---------------------------------------------------------------------------
# Validation: donate
# ---------------------------------------------------------------------------

def test_validate_donate_negative():
    ok, reason = sects.validate_donate(0, 100)
    assert ok is False and "positive" in reason
    ok, reason = sects.validate_donate(-5, 100)
    assert ok is False


def test_validate_donate_insufficient():
    ok, reason = sects.validate_donate(200, 100)
    assert ok is False and "only have" in reason


def test_validate_donate_valid():
    ok, _ = sects.validate_donate(50, 100)
    assert ok is True
    ok, _ = sects.validate_donate(100, 100)  # exact
    assert ok is True


# ---------------------------------------------------------------------------
# Validation: upgrade
# ---------------------------------------------------------------------------

def test_validate_upgrade_max_level():
    ok, reason = sects.validate_upgrade(sects.SECT_MAX_ARRAY_LEVEL, 99999)
    assert ok is False and "pinnacle" in reason


def test_validate_upgrade_insufficient():
    cost = sects.array_upgrade_cost(1)
    ok, reason = sects.validate_upgrade(1, cost - 1)
    assert ok is False and "requires" in reason


def test_validate_upgrade_valid():
    cost = sects.array_upgrade_cost(1)
    ok, _ = sects.validate_upgrade(1, cost)
    assert ok is True


# ---------------------------------------------------------------------------
# Validation: promote
# ---------------------------------------------------------------------------

def test_validate_promote_hierarchy():
    patriarch = sects.rank_index("Patriarch")   # 4
    elder = sects.rank_index("Elder")           # 3
    core = sects.rank_index("Core Disciple")    # 2
    outer = sects.rank_index("Outer Disciple")  # 0

    # Patriarch promotes Elder → not valid (Elder is already one step below)
    ok, _ = sects.validate_promote(patriarch, elder)
    assert ok is True
    # Promote Core Disciple → not valid (skips a step)
    ok, _ = sects.validate_promote(patriarch, core)
    assert ok is False
    # Promote yourself → not valid
    ok, _ = sects.validate_promote(patriarch, patriarch)
    assert ok is False
    # Promote someone above you → not valid
    ok, _ = sects.validate_promote(elder, patriarch)
    assert ok is False


# ---------------------------------------------------------------------------
# Validation: demote
# ---------------------------------------------------------------------------

def test_validate_demote_hierarchy():
    patriarch = sects.rank_index("Patriarch")   # 4
    elder = sects.rank_index("Elder")           # 3
    inner = sects.rank_index("Inner Disciple")  # 1
    outer = sects.rank_index("Outer Disciple")  # 0

    # Patriarch demotes Elder → valid
    ok, _ = sects.validate_demote(patriarch, elder)
    assert ok is True
    # Patriarch demotes Inner Disciple → valid (big jump allowed)
    ok, _ = sects.validate_demote(patriarch, inner)
    assert ok is True
    # Can't demote someone at or above your rank
    ok, _ = sects.validate_demote(elder, patriarch)
    assert ok is False
    # Can't demote someone already at bottom
    ok, _ = sects.validate_demote(patriarch, outer)
    assert ok is False  # outer is index 0, already lowest


# ---------------------------------------------------------------------------
# Validation: expel
# ---------------------------------------------------------------------------

def test_validate_expel():
    patriarch = sects.rank_index("Patriarch")   # 4
    elder = sects.rank_index("Elder")           # 3
    outer = sects.rank_index("Outer Disciple")  # 0

    # Patriarch expels Outer → valid
    ok, _ = sects.validate_expel(patriarch, outer)
    assert ok is True
    # Patriarch expels Elder → valid
    ok, _ = sects.validate_expel(patriarch, elder)
    assert ok is True
    # Can't expel equal rank
    ok, _ = sects.validate_expel(elder, elder)
    assert ok is False
    # Can't expel higher rank
    ok, _ = sects.validate_expel(outer, patriarch)
    assert ok is False
