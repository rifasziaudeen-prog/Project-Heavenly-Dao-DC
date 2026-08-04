"""Sect engine — organizational mechanics (Phase 2 social core).

A sect is a player-run organization that grants array bonuses to all members.
All rules here are deterministic and auditable (no LLM, no RNG for validation).
The patriarch manages recruits, rank promotions, treasury spending, and array
upgrades.
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Rank hierarchy (index 0 = lowest, 4 = highest)
# ---------------------------------------------------------------------------
SECT_RANKS = [
    "Outer Disciple",
    "Inner Disciple",
    "Core Disciple",
    "Elder",
    "Patriarch",
]

SECT_RANK_LABELS: dict[str, str] = {
    "Outer Disciple": "外门弟子 Outer Disciple",
    "Inner Disciple": "内门弟子 Inner Disciple",
    "Core Disciple": "核心弟子 Core Disciple",
    "Elder": "长老 Elder",
    "Patriarch": "掌门 Patriarch",
}

# ---------------------------------------------------------------------------
# Rule constants
# ---------------------------------------------------------------------------
SECT_CREATE_MIN_TIER = 3        # Foundation Establishment to found a sect
SECT_MAX_NAME_LENGTH = 40
SECT_MAX_ARRAY_LEVEL = 7         # level 7 = +56% capped to ARRAY_BONUS_CAP (+50%)
ARRAY_UPGRADE_BASE_COST = 500    # cost = int(500 * 1.5^(level-1))
SPIRIT_STONES_PER_BREAKTHROUGH = 10  # earned on successful breakthrough

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rank_index(rank_name: str) -> int:
    """Parse a rank string to its hierarchy index. Unknown ranks → 0."""
    for idx, name in enumerate(SECT_RANKS):
        if name.lower() == rank_name.lower():
            return idx
    return 0


def rank_label(rank_name: str) -> str:
    return SECT_RANK_LABELS.get(rank_name, rank_name)


def next_rank(current_idx: int) -> int | None:
    """Index of the rank above, or None if already at the top."""
    if current_idx >= len(SECT_RANKS) - 1:
        return None
    return current_idx + 1


def prev_rank(current_idx: int) -> int | None:
    """Index of the rank below, or None if already at the bottom."""
    if current_idx <= 0:
        return None
    return current_idx - 1


# ---------------------------------------------------------------------------
# Economy
# ---------------------------------------------------------------------------

def array_upgrade_cost(current_level: int) -> int:
    """Spirit stones required to upgrade from *current_level* to current+1.

    Exponential scaling: ``int(500 × 1.5^(level-1))``.
    Level 1→2 costs 500, level 6→7 costs 3,797.
    """
    return int(ARRAY_UPGRADE_BASE_COST * 1.5 ** (current_level - 1))


def array_bonus_pct(level: int) -> float:
    """Qi bonus percentage for display (matches core/math.py ARRAY_BONUS_CAP)."""
    return min(level * 0.08, 0.50) * 100.0


# ---------------------------------------------------------------------------
# Validation — all return (ok, reason)
# ---------------------------------------------------------------------------

def validate_sect_creation(name: str, creator_tier: int) -> tuple[bool, str]:
    if len(name) > SECT_MAX_NAME_LENGTH or len(name) < 2:
        return False, (
            f"Sect name must be between 2 and {SECT_MAX_NAME_LENGTH} characters."
        )
    if creator_tier < SECT_CREATE_MIN_TIER:
        return False, (
            f"Only cultivators at **Foundation Establishment (筑基, tier {SECT_CREATE_MIN_TIER})**"
            " or above may found a sect."
        )
    return True, "valid"


def validate_join(
    has_sect: bool,
    max_members: int,
    current_count: int,
) -> tuple[bool, str]:
    if has_sect:
        return False, (
            "You already belong to a sect. `/sect leave` first before joining another."
        )
    if current_count >= max_members:
        return False, (
            "This sect has reached its member capacity. Seek another path."
        )
    return True, "valid"


def validate_donate(amount: int, balance: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Donation must be a positive number of spirit stones."
    if amount > balance:
        return False, (
            f"You only have **{balance:,}** spirit stones. "
            f"Cultivate and breakthrough to earn more."
        )
    return True, "valid"


def validate_upgrade(array_level: int, treasury: int) -> tuple[bool, str]:
    if array_level >= SECT_MAX_ARRAY_LEVEL:
        return False, (
            f"The sect array is already at its pinnacle (**level {SECT_MAX_ARRAY_LEVEL}**). "
            "No further upgrades are possible."
        )
    cost = array_upgrade_cost(array_level)
    if treasury < cost:
        return False, (
            f"Upgrade requires **{cost:,}** spirit stones; "
            f"the treasury holds only **{treasury:,}**."
        )
    return True, "valid"


def validate_promote(
    actor_rank_idx: int,
    target_rank_idx: int,
) -> tuple[bool, str]:
    """Patriarch can promote a member by exactly one rank step and never past
    their own rank."""
    if target_rank_idx >= actor_rank_idx:
        return False, (
            "You cannot promote someone to your rank or above."
        )
    if target_rank_idx != actor_rank_idx - 1:
        return False, (
            "You may only promote one rank step at a time. "
            "Promote them to the rank directly below yours."
        )
    return True, "valid"


def validate_demote(
    actor_rank_idx: int,
    target_rank_idx: int,
) -> tuple[bool, str]:
    """Patriarch can demote any member below their own rank, but not below
    Outer Disciple (index 0)."""
    if target_rank_idx >= actor_rank_idx:
        return False, (
            "You cannot demote someone at or above your own rank."
        )
    if target_rank_idx <= 0:
        return False, (
            f"They are already at the lowest rank ({SECT_RANK_LABELS[SECT_RANKS[0]]}). "
            "Expel them instead if they are unworthy."
        )
    return True, "valid"


def validate_expel(
    actor_rank_idx: int,
    target_rank_idx: int,
) -> tuple[bool, str]:
    """Cannot expel someone at or above your own rank."""
    if target_rank_idx >= actor_rank_idx:
        return False, (
            "You cannot expel someone at or above your own rank."
        )
    return True, "valid"
