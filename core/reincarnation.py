"""Deterministic reincarnation engine.

Pure Python logic for legacy calculation, rebirth stats, physique naming,
epitaph generation, and memory unlocks — no Discord or DB dependencies.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

PHYSIQUE_NAMES: Dict[int, str] = {
    0: "Mortal Meridian",
    1: "Reincarnated Soul 转世之魂",
    2: "Twice-Born Dao Heart 二世道心",
    3: "Karmic Body 因果之体",
    4: "Eternal Return Vessel 轮回之器",
    5: "Heavenly Dao Reject 天道弃子",
}

EPITAPH_TEMPLATES = [
    "Here lies {name}, who walked {realms} realms and accumulated {qi} Qi. The Dao was cruel, but {pronoun} legacy endures.",
    "{name} fell at {highest_realm}, yet {pronoun} soul refuses dispersal. Cycle {cycle} begins.",
    "The heavens wept when {name} perished. {lifetime_qi} Qi scattered, but {pronoun} comprehension remains.",
    "{name} endured {karma} karma and {breakthroughs} breakthroughs. For {pronoun} Dao, this is not an end — but a return.",
]


def can_voluntary_reincarnate(cultivator: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if player can voluntarily reincarnate (Tier 5+, half-full dantian)."""
    realm_tier = cultivator.get("realm_tier", 1)
    qi_current = cultivator.get("qi_current", 0)
    qi_capacity = cultivator.get("qi_capacity", 1000)

    if realm_tier < 5:
        return False, "You must reach Nascent Soul (tier 5) to comprehend the cycle of rebirth."

    if qi_current < qi_capacity * 0.5:
        return False, "Your dantian must be at least half-full to trigger voluntary reincarnation."

    return True, None


def get_physique_name(cycle: int) -> str:
    """Unique physique name based on reincarnation cycle count."""
    return PHYSIQUE_NAMES.get(min(cycle, 5), PHYSIQUE_NAMES[5])


def generate_epitaph(cultivator: Dict[str, Any]) -> str:
    """Generate cached epitaph from template engine."""
    template = random.choice(EPITAPH_TEMPLATES)
    pronoun = "her" if cultivator.get("gender") == "female" else "his"

    return template.format(
        name=cultivator.get("username", "Cultivator"),
        realms=cultivator.get("realm_tier", 1),
        qi=cultivator.get("qi_current", 0),
        pronoun=pronoun,
        highest_realm=f"Tier {cultivator.get('realm_tier', 1)} Stage {cultivator.get('realm_sub_stage', 1)}",
        cycle=cultivator.get("reincarnation_cycle", 0) + 1,
        lifetime_qi=cultivator.get("qi_current", 0),
        karma=cultivator.get("karma_points", 0),
        breakthroughs=cultivator.get("total_breakthroughs", 0),
        failures=cultivator.get("failure_streak", 0),
    )


def select_retained_technique(inventory: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """Pick one technique scroll to retain from inventory (equipped preferred)."""
    if not inventory:
        return None

    equipped_techs = [
        item["name"] for item in inventory
        if item.get("item_type") == "Technique_Scroll" and item.get("is_equipped")
    ]
    if equipped_techs:
        return random.choice(equipped_techs)

    any_techs = [
        item["name"] for item in inventory
        if item.get("item_type") == "Technique_Scroll"
    ]
    if any_techs:
        return random.choice(any_techs)

    return None


def calculate_legacy(
    cultivator: Dict[str, Any],
    inventory: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Calculate retained stats, bonuses, and technique for rebirth."""
    cycle = cultivator.get("reincarnation_cycle", 0)
    comp = cultivator.get("comprehension", 10)
    luck = cultivator.get("luck", 5)
    stat_pts = cultivator.get("stat_points", 0)

    retained = {
        "comprehension": max(1, int(comp * 0.25)),
        "luck": max(1, int(luck * 0.10)),
        "stat_points": max(0, int(stat_pts * 0.50)),
        "technique": select_retained_technique(inventory) or cultivator.get("inherited_technique"),
    }

    cycle_bonus = {
        "breakthrough_bonus": min(0.25, (cycle + 1) * 0.05),  # +5% per cycle, max +25%
        "starting_qi_bonus": cycle * 100,                     # extra starting Qi
        "comprehension_bonus": cycle * 2,                     # extra comprehension on rebirth
    }

    return {
        "retained_stats": retained,
        "cycle_bonus": cycle_bonus,
        "epitaph": generate_epitaph(cultivator),
    }


def calculate_rebirth_stats(base_stats: Dict[str, int], legacy: Dict[str, Any]) -> Dict[str, int]:
    """Combine base Mortal stats + retained legacy + cycle bonuses."""
    retained = legacy["retained_stats"]
    cycle = legacy["cycle_bonus"]

    return {
        "strength": base_stats.get("strength", 10),
        "spirit": base_stats.get("spirit", 10),
        "physique": base_stats.get("physique", 10),
        "comprehension": base_stats.get("comprehension", 10) + retained["comprehension"] + cycle["comprehension_bonus"],
        "luck": base_stats.get("luck", 5) + retained["luck"],
        "stat_points": retained["stat_points"],
    }


def unlock_memory(cultivator: Dict[str, Any], existing_memories: Optional[List[str]] = None) -> Optional[str]:
    """Unlock past life memories at comprehension thresholds (100, 250, 500, 1000)."""
    memories = existing_memories or []
    cycle = cultivator.get("reincarnation_cycle", 0)
    comp = cultivator.get("comprehension", 10)

    if cycle == 0:
        return None

    if comp >= 1000 and "ultimate_truth" not in memories:
        return f"You remember your ultimate truth: you have died and returned {cycle} times. The Dao fears you."

    if comp >= 500 and "technique_origin" not in memories:
        tech = cultivator.get("inherited_technique") or "Ancient Mantra"
        return f"You recall the origin of your technique '{tech}': it was forged in your {cycle}th life."

    if comp >= 250 and "death_memory" not in memories:
        return "A flash of memory: your previous death. The pain, the dispersal, the return. You shudder."

    if comp >= 100 and "first_memory" not in memories:
        return "Whispers from a past life echo in your mind. You were someone else once. Someone stronger?"

    return None


def execute_rebirth_payload(
    cultivator: Dict[str, Any],
    inventory: Optional[List[Dict[str, Any]]] = None,
    reason: str = "voluntary",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generate database update dictionary and log entry for a cultivator rebirth.

    Returns (cultivator_updates: dict, log_entry: dict)
    """
    cycle_from = cultivator.get("reincarnation_cycle", 0)
    cycle_to = cycle_from + 1

    legacy = calculate_legacy(cultivator, inventory)
    base_mortal = {"strength": 10, "spirit": 10, "physique": 10, "comprehension": 10, "luck": 5}
    new_stats = calculate_rebirth_stats(base_mortal, legacy)
    physique_name = get_physique_name(cycle_to)

    # Transcendence capacity bonus survives rebirth (it is a permanent gift)
    transcendent_cap = int(cultivator.get("transcendence_capacity_bonus", 0) or 0)
    cultivator_updates = {
        "realm_tier": 1,
        "realm_sub_stage": 1,
        "qi_current": legacy["cycle_bonus"]["starting_qi_bonus"],
        "qi_capacity": 1000 + transcendent_cap,
        "strength": new_stats["strength"],
        "spirit": new_stats["spirit"],
        "physique": new_stats["physique"],
        "comprehension": new_stats["comprehension"],
        "luck": new_stats["luck"],
        "stat_points": new_stats["stat_points"],
        "heart_demon_ratio": 0.0,
        "failure_streak": 0,
        "reincarnation_cycle": cycle_to,
        "cultivation_physique": physique_name,
        "inherited_technique": legacy["retained_stats"]["technique"],
        "reincarnation_breakthrough_bonus": legacy["cycle_bonus"]["breakthrough_bonus"],
    }

    log_entry = {
        "cultivator_id": cultivator["id"],
        "cycle_from": cycle_from,
        "cycle_to": cycle_to,
        "reason": reason,
        "realm_tier_at_death": cultivator.get("realm_tier", 1),
        "realm_sub_stage_at_death": cultivator.get("realm_sub_stage", 1),
        "comprehension_retained": legacy["retained_stats"]["comprehension"],
        "luck_retained": legacy["retained_stats"]["luck"],
        "technique_retained": legacy["retained_stats"]["technique"],
        "epitaph": legacy["epitaph"],
    }

    return cultivator_updates, log_entry
