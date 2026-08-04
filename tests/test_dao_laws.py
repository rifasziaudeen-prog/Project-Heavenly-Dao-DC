"""Pure logic unit tests for Dao Laws (core/dao_laws.py)."""
import random
from core import dao_laws as core_dl


def test_can_comprehend_law_gates():
    law = {"name": "Law of Space", "realm_required": 5, "comprehension_required": 200}

    # Low realm
    ok, err = core_dl.can_comprehend_law({"realm_tier": 4, "comprehension": 300}, law)
    assert not ok and "realm tier 5" in err

    # Low comprehension
    ok, err = core_dl.can_comprehend_law({"realm_tier": 5, "comprehension": 100}, law)
    assert not ok and "200 Comprehension" in err

    # Ready
    ok, err = core_dl.can_comprehend_law({"realm_tier": 5, "comprehension": 250}, law)
    assert ok and err is None


def test_calculate_insight_gain():
    random.seed(42)
    gain_comp = core_dl.calculate_insight_gain("comprehend")
    assert 1.0 <= gain_comp <= 3.0

    gain_trib = core_dl.calculate_insight_gain("tribulation")
    assert 5.0 <= gain_trib <= 10.0


def test_check_milestones():
    # Crossing 25%
    crossed = core_dl.check_milestones(26.5, 23.0)
    assert crossed == [25]

    # Crossing multiple (e.g. big tribulation gain from 22% to 52%)
    crossed_multi = core_dl.check_milestones(52.0, 22.0)
    assert crossed_multi == [25, 50]

    # Crossing 100%
    crossed_max = core_dl.check_milestones(100.0, 95.0)
    assert crossed_max == [100]


def test_resolve_law_effects():
    cultivator_laws = [
        {
            "mastery_percentage": 55.0,
            "mastery_effect": '{"25": {"damage_bonus": 0.15}, "50": {"technique": "Sword Intent"}}',
        },
        {
            "mastery_percentage": 80.0,
            "mastery_effect": '{"25": {"dodge_bonus": 0.10}, "75": {"breakthrough_bonus": 0.20}}',
        },
    ]

    effects = core_dl.resolve_law_effects(cultivator_laws)
    assert effects["damage_bonus"] == 0.15
    assert effects["dodge_bonus"] == 0.10
    assert effects["breakthrough_bonus"] == 0.20
    assert "Sword Intent" in effects["unlocked_techniques"]


def test_has_dao_fusion_requirement():
    laws_low = [{"mastery_percentage": 45.0}, {"mastery_percentage": 99.5}]
    assert not core_dl.has_dao_fusion_requirement(laws_low)

    laws_fusion_ready = [{"mastery_percentage": 45.0}, {"mastery_percentage": 100.0}]
    assert core_dl.has_dao_fusion_requirement(laws_fusion_ready)
