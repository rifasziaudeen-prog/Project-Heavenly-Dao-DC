"""Deterministic world events engine.

Pure Python logic for damage calculation, boss phase transitions,
sect sacrifice mechanics, reward distributions, and (since v1.11.0) the
World-boss Contendance exchange — no Discord or DB dependencies.

World-boss Contendance (Part 5 · Commit 3): the boss telegraphs a scripted
intent pattern; each attacker resolves one exchange with the shared combat
engine (core/combat.resolve_round). All tuning numbers are named constants
right here.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

from core.combat import resolve_round


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


# ---------------------------------------------------------------------------
# World-boss Contendance (Part 5 · Commit 3) — scripted intent patterns
# ---------------------------------------------------------------------------
# Each event type cycles a scripted intent pattern (index = the attacker's
# boss_round). Kinds:
#   'unfold'    — the boss gathers Sword Intent to unleash; a player who
#                 unfolds Law of Sword 2+ ranks ahead COUNTERS it, otherwise
#                 an unfold still blocks some of its power.
#   'technique' — a heavy strike (parried by artifact, blocked by unfold).
#   'pass'      — the boss regroups; it does not attack this round.
BOSS_INTENT_PATTERNS: Dict[str, List[str]] = {
    "demon_beast_siege":      ["unfold", "technique", "technique", "unfold", "pass", "technique"],
    "heavenly_tribulation_rain": ["technique", "unfold", "technique", "unfold", "technique"],
    "ancient_ruin_awakening": ["pass", "unfold", "technique", "unfold", "unfold", "technique"],
    "sect_war":               ["technique", "technique", "unfold", "technique", "unfold"],
    "dao_competition":        ["unfold", "technique", "unfold", "pass", "technique"],
}

# The boss's unleash is always the endgame Sword Law, rank 1 — a player who
# owns Law of Sword at rank 3+ (2 ranks ahead) can counter it.
BOSS_UNFOLD_LAW = "Law of Sword"
BOSS_UNFOLD_RANK = 1

# Flat boss strike power per phase (1 weakest → 5 strongest).
BOSS_PHASE_POWER: Dict[int, int] = {1: 18, 2: 24, 3: 30, 4: 38, 5: 48}

# Player combat damage → the colossal boss HP bar (1 point of combat damage
# crushes 30 points of the boss's vitality).
BOSS_DAMAGE_SCALE = 30

# Player stakes on the world-boss field.
BOSS_HP_REGEN_PER_HOUR = 20      # flat HP recovered per hour away from the fight
BOSS_DEFEAT_HD_RATIO = 0.05      # +1 Heart Demon Point when overwhelmed
BOSS_DEFEAT_COOLDOWN = 30        # minutes before re-engaging after defeat
BOSS_PILL_HEAL = 25              # flat HP restored by the pill intent


def boss_intent_for(event_type: str, round_index: int) -> str:
    """The boss's scripted intent at the attacker's round index."""
    pattern = BOSS_INTENT_PATTERNS.get(event_type, ["technique"])
    return pattern[round_index % len(pattern)]


def build_boss_intent(event_type: str, phase: int, round_index: int) -> Dict[str, Any]:
    """Build the boss's round-intent dict (side A) for resolve_round."""
    kind = boss_intent_for(event_type, round_index)
    power = BOSS_PHASE_POWER.get(phase, BOSS_PHASE_POWER[1])
    if kind == "technique":
        return {
            "kind": "technique",
            "technique": {"base_damage": power, "stored_qi_cost": 0, "law_affinity": None},
            "entries": [], "rank": 1, "law": None,
            "laws": {}, "stats": {"physique": 10, "spirit": 10}, "parry": 0,
        }
    if kind == "unfold":
        return {
            "kind": "unfold",
            "technique": None, "entries": [], "rank": 1,
            "law": {"name": BOSS_UNFOLD_LAW, "rank": BOSS_UNFOLD_RANK},
            "laws": {}, "stats": {"physique": 10, "spirit": 10}, "parry": 0,
        }
    # pass — the boss regroups; it deals no damage this round.
    return {
        "kind": "pass",
        "technique": None, "entries": [], "rank": 1, "law": None,
        "laws": {}, "stats": {"physique": 10, "spirit": 10}, "parry": 0,
    }


def boss_stance_label(event_type: str, round_index: int, lang: str = "english") -> str:
    """Human label for the boss's telegraphed stance at this round index."""
    kind = boss_intent_for(event_type, round_index)
    if kind == "unfold":
        return ("gathers Sword Intent to unleash 剑意凝聚" if lang == "chinese"
                else "gathers Sword Intent to unleash")
    if kind == "technique":
        return "rears back for a devastating strike" if lang == "english" else "蓄势欲发雷霆一击"
    return "regroups and recovers its stance" if lang == "english" else "重整旗鼓"


def resolve_boss_exchange(
    player_intent: Dict[str, Any],
    event_type: str,
    phase: int,
    round_index: int,
    d20_player: int = 0,
    d20_boss: int = 0,
) -> Dict[str, Any]:
    """Resolve one attacker's exchange against the world boss.

    The boss fights as side A, the player as side B, so the shared engine's
    semantics map directly:
      damage_a  -> damage dealt TO the boss (scaled by BOSS_DAMAGE_SCALE)
      damage_b  -> damage the boss deals to the PLAYER (raw HP loss)
    The player's unfold counters the boss's Sword-Law unleash when it is 2+
    ranks ahead (the existing resolve_round counter rule).
    """
    boss = build_boss_intent(event_type, phase, round_index)
    outcome = resolve_round(boss, player_intent, d20_boss, d20_player)
    return {
        "kind": outcome["kind"],
        "notes": outcome["notes"],
        "boss_intent": boss_intent_for(event_type, round_index),
        "damage_to_boss": outcome["damage_a"] * BOSS_DAMAGE_SCALE,
        "damage_to_player": outcome["damage_b"],
    }


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
