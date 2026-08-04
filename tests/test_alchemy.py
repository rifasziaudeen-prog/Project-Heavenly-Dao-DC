"""Tests for the deterministic alchemy engine (core/alchemy.py)."""
import random
import pytest

from core.alchemy import (
    AlchemyResult,
    calculate_qi_cost,
    calculate_success_rate,
    resolve_explosion_effect,
    resolve_failure_effect,
    resolve_success_effect,
    roll_result,
    score_fire_control,
    score_ingredient_order,
    score_spiritual_sense,
    validate_recipe_access,
)


def test_fire_control_perfect():
    assert score_fire_control(["Low", "Medium", "High"], ["Low", "Medium", "High"]) == 10


def test_fire_control_partial():
    assert score_fire_control(["Low", "Low", "High"], ["Low", "Medium", "High"]) == 7


def test_fire_control_wrong_length():
    assert score_fire_control(["Low"], ["Low", "Medium", "High"]) == 4


def test_ingredient_order_perfect():
    assert score_ingredient_order(["A", "B", "C"], ["A", "B", "C"]) == 10


def test_ingredient_order_partial():
    assert score_ingredient_order(["A", "C", "B"], ["A", "B", "C"]) == 3


def test_spiritual_sense_high_comprehension():
    random.seed(42)
    score = score_spiritual_sense(comprehension=100, recipe_difficulty=50)
    assert score in (8, 10)


def test_spiritual_sense_low_comprehension():
    random.seed(42)
    score = score_spiritual_sense(comprehension=10, recipe_difficulty=80)
    assert score <= 4


def test_success_rate_max():
    rate = calculate_success_rate(0.65, 10, "primordial", 10, 10, 10)
    assert rate == 0.95  # clamped at max


def test_success_rate_min():
    rate = calculate_success_rate(0.10, 0, "none", 1, 1, 1)
    assert rate == 0.05  # clamped at min


def test_success_rate_typical():
    rate = calculate_success_rate(0.50, 2, "bronze", 5, 6, 5)
    assert 0.5 < rate < 0.9


def test_roll_result_miracle():
    random.seed(0)  # Deterministic for test
    result = roll_result(0.5)
    assert isinstance(result, AlchemyResult)


def test_roll_result_explosion_threshold():
    # If final_rate < 0.3 and roll > 0.7, explosion
    random.seed(12)
    res = roll_result(0.10)
    assert res in (AlchemyResult.FAILURE, AlchemyResult.EXPLOSION)


def test_resolve_success_effect_standard():
    eff = {"type": "qi_boost", "amount": 500}
    resolved = resolve_success_effect(eff, miracle=False)
    assert resolved["amount"] == 500


def test_resolve_success_effect_miracle():
    eff = {"type": "qi_boost", "amount": 500}
    resolved = resolve_success_effect(eff, miracle=True)
    assert resolved["amount"] == 750  # 1.5x multiplier


def test_resolve_failure_and_explosion_effects():
    fail_eff = {"type": "poison", "heart_demon_delta": 0.02}
    exp_eff = {"type": "explosion", "qi_loss_pct": 0.25}
    assert resolve_failure_effect(fail_eff) == fail_eff
    assert resolve_explosion_effect(exp_eff) == exp_eff


def test_validate_recipe_realm_tier_gate():
    recipe = {"required_realm_tier": 3, "required_alchemy_mastery": 0, "ingredients": []}
    ok, err = validate_recipe_access(recipe, 2, 0, [])
    assert not ok
    assert "realm tier 3" in err.lower()


def test_validate_recipe_mastery_gate():
    recipe = {"required_realm_tier": 1, "required_alchemy_mastery": 5, "ingredients": []}
    ok, err = validate_recipe_access(recipe, 2, 2, [])
    assert not ok
    assert "alchemy mastery 5" in err.lower()


def test_validate_recipe_missing_ingredient():
    recipe = {
        "required_realm_tier": 1,
        "required_alchemy_mastery": 0,
        "ingredients": [{"item_name": "Spirit Grass", "quantity": 3, "grade_min": "Mortal"}],
    }
    inventory = [{"name": "Spirit Grass", "quantity": 1, "grade": "Mortal"}]
    ok, err = validate_recipe_access(recipe, 2, 0, inventory)
    assert not ok
    assert "Missing 3x Spirit Grass" in err


def test_validate_recipe_sufficient():
    recipe = {
        "required_realm_tier": 1,
        "required_alchemy_mastery": 0,
        "ingredients": [{"item_name": "Spirit Grass", "quantity": 3, "grade_min": "Mortal"}],
    }
    inventory = [{"name": "Spirit Grass", "quantity": 5, "grade": "Mortal"}]
    ok, err = validate_recipe_access(recipe, 2, 0, inventory)
    assert ok
    assert err is None


def test_validate_recipe_higher_grade_ingredient_accepted():
    recipe = {
        "required_realm_tier": 1,
        "required_alchemy_mastery": 0,
        "ingredients": [{"item_name": "Spirit Herb", "quantity": 2, "grade_min": "Mortal"}],
    }
    inventory = [{"name": "Spirit Herb", "quantity": 2, "grade": "Earth"}]
    ok, err = validate_recipe_access(recipe, 2, 0, inventory)
    assert ok


def test_qi_cost_scaling():
    assert calculate_qi_cost("Mortal") == 50
    assert calculate_qi_cost("Earth") == 200
    assert calculate_qi_cost("Heaven") == 500
    assert calculate_qi_cost("Immortal") == 1500
    assert calculate_qi_cost("God") == 5000
    assert calculate_qi_cost("Unknown") == 100
