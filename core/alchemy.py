"""Deterministic alchemy engine.

No Discord dependencies, no database access — pure Python functions.
"""
from __future__ import annotations

from enum import Enum
import math
import random
from typing import Any, Dict, List, Optional, Tuple

GRADE_RANK = {
    "Mortal": 1,
    "Earth": 2,
    "Heaven": 3,
    "Immortal": 4,
    "God": 5,
}


class AlchemyResult(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    EXPLOSION = "explosion"
    MIRACLE = "miracle"  # 1% chance: upgraded grade & 1.5x effect multiplier


# ============================================================================
# STAGE SCORING
# ============================================================================
def score_fire_control(player_pattern: List[str], correct_pattern: List[str]) -> int:
    """Stage 1: Fire Control Rhythm Game.

    Player repeats a shown pattern [Low, Medium, High].
    Score 1-10 based on pattern match accuracy.
    """
    if len(player_pattern) != len(correct_pattern):
        return max(1, 10 - abs(len(player_pattern) - len(correct_pattern)) * 3)

    matches = sum(1 for p, c in zip(player_pattern, correct_pattern) if p == c)
    return max(1, min(10, int(round(matches / len(correct_pattern) * 10))))


def score_ingredient_order(player_order: List[str], correct_order: List[str]) -> int:
    """Stage 2: Ingredient Ordering.

    Score 1-10 based on relative ordering correctness.
    """
    if player_order == correct_order:
        return 10

    correct_positions = sum(1 for p, c in zip(player_order, correct_order) if p == c)
    return max(3, int(correct_positions / len(correct_order) * 8))


def score_spiritual_sense(comprehension: int, recipe_difficulty: int) -> int:
    """Stage 3: Spiritual Sense Check.

    Comprehension stat roll vs recipe difficulty.
    """
    roll = random.gauss(mu=comprehension, sigma=max(1.0, comprehension * 0.2))
    ratio = roll / max(1, recipe_difficulty)

    if ratio >= 1.5:
        return 10
    elif ratio >= 1.0:
        return 8
    elif ratio >= 0.8:
        return 6
    elif ratio >= 0.6:
        return 4
    else:
        return max(1, int(ratio * 5))


# ============================================================================
# SUCCESS RATE CALCULATION
# ============================================================================
CAULDRON_BONUS: Dict[str, float] = {
    "none": 0.0,
    "bronze": 0.05,
    "mystic": 0.10,
    "heavenly": 0.15,
    "primordial": 0.20,
}


def calculate_success_rate(
    base_rate: float,
    alchemy_mastery: int,
    cauldron_grade: str,
    fire_score: int,
    ingredient_score: int,
    sense_score: int,
) -> float:
    """Final success rate before RNG roll, clamped to [0.05, 0.95]."""
    mastery_bonus = alchemy_mastery * 0.02
    cauldron_bonus = CAULDRON_BONUS.get(cauldron_grade.lower(), 0.0)

    fire_bonus = fire_score * 0.03
    ingredient_bonus = (ingredient_score - 5) * 0.02
    sense_bonus = (sense_score - 5) * 0.02

    total = base_rate + mastery_bonus + cauldron_bonus + fire_bonus + ingredient_bonus + sense_bonus
    return max(0.05, min(0.95, total))


def roll_result(final_rate: float) -> AlchemyResult:
    """RNG roll with 1% miracle chance and low-rate explosion risk."""
    roll = random.random()

    # 1% miracle: upgraded pill grade & boosted output
    if roll < 0.01:
        return AlchemyResult.MIRACLE

    # Explosion threshold: if final_rate < 0.3 and roll > 0.7
    if final_rate < 0.3 and roll > 0.7:
        return AlchemyResult.EXPLOSION

    if roll < final_rate:
        return AlchemyResult.SUCCESS

    return AlchemyResult.FAILURE


# ============================================================================
# EFFECT RESOLUTION
# ============================================================================
def resolve_success_effect(effect_data: Dict[str, Any], miracle: bool = False) -> Dict[str, Any]:
    """Parse effect_on_success JSON and apply 1.5x miracle multiplier if miracle occurs."""
    result = dict(effect_data)
    if miracle:
        for key, value in result.items():
            if isinstance(value, (int, float)) and key != "type":
                result[key] = value * 1.5
    return result


def resolve_failure_effect(effect_data: Dict[str, Any]) -> Dict[str, Any]:
    return dict(effect_data)


def resolve_explosion_effect(effect_data: Dict[str, Any]) -> Dict[str, Any]:
    return dict(effect_data)


# ============================================================================
# VALIDATION & COST
# ============================================================================
def validate_recipe_access(
    recipe: Dict[str, Any],
    cultivator_realm_tier: int,
    cultivator_mastery: int,
    inventory: List[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    """Check if cultivator can attempt this recipe based on realm, mastery, and ingredients."""
    if cultivator_realm_tier < recipe.get("required_realm_tier", 1):
        return False, f"Requires realm tier {recipe.get('required_realm_tier', 1)} or higher."

    if cultivator_mastery < recipe.get("required_alchemy_mastery", 0):
        return False, f"Requires alchemy mastery {recipe.get('required_alchemy_mastery', 0)}."

    ingredients = recipe.get("ingredients", [])
    if isinstance(ingredients, str):
        import json
        try:
            ingredients = json.loads(ingredients)
        except Exception:
            ingredients = []

    for ing in ingredients:
        req_name = ing["item_name"]
        req_qty = ing["quantity"]
        req_grade_min = ing.get("grade_min", "Mortal")
        min_rank = GRADE_RANK.get(req_grade_min, 1)

        found_qty = sum(
            item.get("quantity", 1) for item in inventory
            if item.get("name") == req_name and GRADE_RANK.get(item.get("grade", "Mortal"), 1) >= min_rank
        )

        if found_qty < req_qty:
            return False, f"Missing {req_qty}x {req_name} (grade {req_grade_min}+). You have {found_qty}."

    return True, None


def calculate_qi_cost(recipe_grade: str) -> int:
    """Qi consumed to attempt refinement."""
    GRADE_QI_COST = {
        "Mortal": 50,
        "Earth": 200,
        "Heaven": 500,
        "Immortal": 1500,
        "God": 5000,
    }
    return GRADE_QI_COST.get(recipe_grade, 100)
