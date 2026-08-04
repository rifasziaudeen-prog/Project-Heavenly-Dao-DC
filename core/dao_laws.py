"""Deterministic Dao Laws engine.

Pure Python logic for law access requirements, insight gains, milestone checks,
effect aggregations, and Dao Fusion gates — no Discord or DB dependencies.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple


def can_comprehend_law(cultivator: Dict[str, Any], law: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if cultivator meets requirements to study a Dao Law (Realm & Comprehension)."""
    req_realm = law.get("realm_required", 5)
    req_comp = law.get("comprehension_required", 200)

    if cultivator.get("realm_tier", 1) < req_realm:
        return False, f"Requires realm tier {req_realm} (Nascent Soul/higher) to comprehend this fundamental law."

    if cultivator.get("comprehension", 10) < req_comp:
        return False, f"Requires {req_comp} Comprehension to grasp the threads of this law. You have {cultivator.get('comprehension', 10)}."

    return True, None


def calculate_insight_gain(source: str = "comprehend") -> float:
    """Calculate random mastery % gain from an enlightenment source."""
    SOURCE_RANGES = {
        "comprehend": (1.0, 3.0),
        "secret_realm": (2.0, 5.0),
        "tribulation": (5.0, 10.0),
        "world_boss": (1.0, 2.0),
        "ancient_text": (1.0, 3.0),
        "sect_meditation": (0.5, 1.0),
    }

    min_val, max_val = SOURCE_RANGES.get(source.lower(), (1.0, 3.0))
    return round(random.uniform(min_val, max_val), 2)


def check_milestones(current_mastery: float, previous_mastery: float) -> List[int]:
    """Check if any new milestone thresholds (25%, 50%, 75%, 100%) were crossed."""
    milestones = [25, 50, 75, 100]
    crossed = []

    for m in milestones:
        if previous_mastery < m <= current_mastery:
            crossed.append(m)

    return crossed


def resolve_law_effects(cultivator_laws: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate active stat bonuses and techniques across all player law masteries."""
    damage_bonus = 0.0
    breakthrough_bonus = 0.0
    cooldown_reduction = 0.0
    dodge_bonus = 0.0
    techniques = []

    for item in cultivator_laws:
        mastery = item.get("mastery_percentage", 0.0)
        effects = item.get("mastery_effect", {})

        if isinstance(effects, str):
            import json
            try:
                effects = json.loads(effects)
            except Exception:
                effects = {}

        if mastery >= 25 and "25" in effects:
            e25 = effects["25"]
            damage_bonus += e25.get("damage_bonus", 0.0)
            dodge_bonus += e25.get("dodge_bonus", 0.0)
            cooldown_reduction += e25.get("cooldown_reduction", 0.0)

        if mastery >= 50 and "50" in effects:
            e50 = effects["50"]
            if "technique" in e50:
                techniques.append(e50["technique"])

        if mastery >= 75 and "75" in effects:
            e75 = effects["75"]
            breakthrough_bonus += e75.get("breakthrough_bonus", 0.0)

    return {
        "damage_bonus": damage_bonus,
        "breakthrough_bonus": breakthrough_bonus,
        "cooldown_reduction": cooldown_reduction,
        "dodge_bonus": dodge_bonus,
        "unlocked_techniques": techniques,
    }


def has_dao_fusion_requirement(cultivator_laws: List[Dict[str, Any]]) -> bool:
    """Check if cultivator has achieved 100.0% mastery in ANY law (required for Dao Fusion)."""
    return any(item.get("mastery_percentage", 0.0) >= 100.0 for item in cultivator_laws)
