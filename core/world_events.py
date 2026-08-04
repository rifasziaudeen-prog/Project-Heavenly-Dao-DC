"""Deterministic world events engine.

Pure Python logic for damage calculation, boss phase transitions,
sect sacrifice mechanics, and reward distributions — no Discord or DB dependencies.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple


def calculate_damage(
    stats: Dict[str, int],
    weapon_bonus: int = 0,
    technique_mult: float = 1.0,
    sect_array_bonus: float = 1.0,
    law_mastery: float = 0.0,
    rng_factor: float = 1.0,
) -> int:
    """Calculate attack damage dealt to a World Boss.

    Formula:
      damage = (strength * 8 + spirit * 4 + weapon_bonus)
               * technique_mult
               * sect_array_bonus
               * (1 + law_mastery / 1000)
               * rng_factor
    """
    str_val = stats.get("strength", 10)
    spi_val = stats.get("spirit", 10)

    base = (str_val * 8 + spi_val * 4 + weapon_bonus)
    mult = technique_mult * sect_array_bonus * (1.0 + law_mastery / 1000.0)

    return max(1, int(base * mult * rng_factor))


def determine_boss_phase(current_hp: int, max_hp: int) -> Tuple[int, str]:
    """Determine boss phase and status narrative based on remaining HP percentage."""
    if max_hp <= 0:
        return 5, "Final Stand"

    ratio = current_hp / max_hp

    if ratio > 0.75:
        return 1, "Phase 1: Normal — The ancient behemoth awakens with roaring thunder."
    elif ratio > 0.50:
        return 2, "Phase 2: Enraged — Blood-red flames shroud the boss (+20% damage)."
    elif ratio > 0.25:
        return 3, "Phase 3: Minions Spawned — Swarms of demonic fiends erupt to shield the master!"
    elif ratio > 0.10:
        return 4, "Phase 4: Desperation — The world trembles as primordial lightning descends!"
    else:
        return 5, "Phase 5: Final Stand — All stats boosted! One final push to slay the beast!"


def calculate_sect_sacrifice_buff(spirit_stones: int) -> Dict[str, Any]:
    """Calculate party-wide sect sacrifice buff based on spirit stones spent from treasury."""
    if spirit_stones >= 1000:
        return {"damage_buff": 0.50, "duration_minutes": 30, "healing": True, "debuff_immunity": True}
    elif spirit_stones >= 500:
        return {"damage_buff": 0.25, "duration_minutes": 20, "healing": True, "debuff_immunity": False}
    elif spirit_stones >= 100:
        return {"damage_buff": 0.10, "duration_minutes": 10, "healing": False, "debuff_immunity": False}
    else:
        return {"damage_buff": 0.0, "duration_minutes": 0, "healing": False, "debuff_immunity": False}


def calculate_event_rewards(participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assign rankings and reward packages to event participants sorted by damage_dealt DESC."""
    sorted_parts = sorted(participants, key=lambda p: p.get("damage_dealt", 0), reverse=True)
    results = []

    for rank, p in enumerate(sorted_parts, start=1):
        if rank == 1:
            reward = {
                "rank": 1,
                "title": "Supreme Slayer · 灭世尊者",
                "item_name": "Heavenly Sword",
                "item_grade": "God",
                "spirit_stones": 500,
            }
        elif rank == 2:
            reward = {
                "rank": 2,
                "title": "Dominator of Calamity · 绝劫主",
                "item_name": "Dragon Core Pill",
                "item_grade": "Immortal",
                "spirit_stones": 300,
            }
        elif rank == 3:
            reward = {
                "rank": 3,
                "title": "Calamity Conqueror · 破劫者",
                "item_name": "Nine Revolutions Spirit Pill",
                "item_grade": "Heaven",
                "spirit_stones": 150,
            }
        elif rank <= 10:
            reward = {
                "rank": rank,
                "title": None,
                "item_name": "Heart Cleansing Pill",
                "item_grade": "Heaven",
                "spirit_stones": 50,
            }
        else:
            reward = {
                "rank": rank,
                "title": None,
                "item_name": "Foundation Pill",
                "item_grade": "Earth",
                "spirit_stones": 10,
            }

        res = dict(p)
        res.update(reward)
        results.append(res)

    return results
