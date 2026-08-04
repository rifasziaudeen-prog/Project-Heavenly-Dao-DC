"""Tests for reaction-role toggle logic (core.server_layout + cogs/reaction_roles)."""
from __future__ import annotations

from core.server_layout import (
    REACTION_ROLE_MAP,
    resolve_reaction_add,
    resolve_reaction_remove,
)
from cogs.reaction_roles import _normalize_emoji

FIRE = "🔥 Fire Affinity 火灵根"
WATER = "💧 Water Affinity 水灵根"
WOOD = "🌿 Wood Affinity 木灵根"
YANG = "☯️ Yang Cultivator"
YIN = "☯️ Yin Cultivator"
SWORD = "🗡️ Sword Saint 剑修"
SCHOLAR = "📜 Dao Scholar 道子"


# --------------------------------------------------------------------------- normalization
def test_emoji_normalization_strips_variation_selector() -> None:
    assert _normalize_emoji("🗡️") == "🗡"
    assert _normalize_emoji("⚔️") == "⚔"
    assert _normalize_emoji("🔥") == "🔥"


def test_all_map_keys_match_normalized_form() -> None:
    for emoji in REACTION_ROLE_MAP:
        assert _normalize_emoji(emoji) == emoji


# --------------------------------------------------------------------------- add
def test_unknown_emoji_is_noop() -> None:
    assert resolve_reaction_add({"any"}, "🚀") == ([], [])


def test_adding_new_role_swaps_exclusive_siblings() -> None:
    to_add, to_remove = resolve_reaction_add({FIRE, WOOD}, "💧")
    assert to_add == [WATER]
    assert set(to_remove) == {FIRE, WOOD}


def test_adding_held_role_is_noop() -> None:
    assert resolve_reaction_add({WATER, SWORD}, "💧") == ([], [])


def test_adding_gender_swaps_other_gender() -> None:
    to_add, to_remove = resolve_reaction_add({YANG}, "🌙")
    assert to_add == [YIN]
    assert to_remove == [YANG]


def test_adding_culture_role_keeps_unrelated_roles() -> None:
    to_add, to_remove = resolve_reaction_add({SWORD, FIRE}, "📜")
    assert to_add == [SCHOLAR]
    assert to_remove == []


# --------------------------------------------------------------------------- remove
def test_remove_drops_held_role_only() -> None:
    assert resolve_reaction_remove({WATER, SWORD}, "💧") == [WATER]
    assert resolve_reaction_remove({SWORD}, "💧") == []
    assert resolve_reaction_remove(set(), "🚀") == []
