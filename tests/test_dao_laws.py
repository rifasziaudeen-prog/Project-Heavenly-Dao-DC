"""Pure logic unit tests for Dao Laws (core/dao_laws.py)."""
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


def test_calculate_insight_gain_is_deterministic_and_aptitude_scaled():
    # Base 2 at low 悟性; +1 per 100 comprehension; flat per-source bonus
    assert core_dl.calculate_insight_gain(10, "comprehend") == 2.0
    assert core_dl.calculate_insight_gain(100, "comprehend") == 3.0
    assert core_dl.calculate_insight_gain(510, "comprehend") == 7.0
    # Sources grant flat bonuses (secret realm +4, tribulation +8)
    assert core_dl.calculate_insight_gain(10, "secret_realm") == 6.0
    assert core_dl.calculate_insight_gain(10, "tribulation") == 10.0
    assert core_dl.calculate_insight_gain(10, "world_boss") == 3.0


def test_check_rank_ups():
    # Crossing 20% -> entering Rank 1
    assert core_dl.check_rank_ups(26.5, 19.0) == [1]
    # Big gain 22 -> 52 crosses 40 (Rank 2)
    assert core_dl.check_rank_ups(52.0, 22.0) == [2]
    # 95 -> 100 crosses the final threshold (Rank 5)
    assert core_dl.check_rank_ups(100.0, 95.0) == [5]
    # No crossing
    assert core_dl.check_rank_ups(30.0, 25.0) == []


def test_law_rank_and_resistance():
    assert core_dl.law_rank(0.0) == 0
    assert core_dl.law_rank(19.9) == 0
    assert core_dl.law_rank(20.0) == 1
    assert core_dl.law_rank(100.0) == 5

    # Resistance: 5% per rank, 25% at Rank 5 (user's chosen curve)
    assert core_dl.law_resistance(20.0) == 0.05
    assert core_dl.law_resistance(59.9) == 0.10   # Rank 2
    assert core_dl.law_resistance(79.0) == 0.15   # Rank 3
    assert core_dl.law_resistance(100.0) == 0.25

    assert "Unranked" in core_dl.law_rank_label(0.0)
    assert core_dl.law_rank_label(60.0) == "Rank 3 · Realization (真悟)"

    # Next-rank progress hints
    assert core_dl.next_rank_progress(25.0) == (15, 40)
    assert core_dl.next_rank_progress(100.0) == (0, 100.0)


def test_law_counter_advantage_is_deterministic():
    # 2+ ranks ahead -> counter (no RNG)
    assert core_dl.law_counter_advantage(100.0, 55.0) is True   # Rank 5 vs 2
    assert core_dl.law_counter_advantage(80.0, 40.0) is True     # Rank 4 vs 2
    assert core_dl.law_counter_advantage(60.0, 40.0) is False    # Rank 3 vs 2
    assert core_dl.law_counter_advantage(55.0, 100.0) is False   # behind


def test_resolve_law_effects_rank_keys():
    cultivator_laws = [
        {
            "mastery_percentage": 55.0,
            "mastery_effect": '{"20": {"damage_bonus": 0.15}, "40": {"technique": "Sword Intent"}}',
        },
        {
            "mastery_percentage": 80.0,
            "mastery_effect": '{"20": {"dodge_bonus": 0.10}, "60": {"breakthrough_bonus": 0.20}}',
        },
    ]

    effects = core_dl.resolve_law_effects(cultivator_laws)
    assert effects["damage_bonus"] == 0.15
    assert effects["dodge_bonus"] == 0.10
    assert effects["breakthrough_bonus"] == 0.20
    assert "Sword Intent" in effects["unlocked_techniques"]


def test_resolve_law_effects_reaches_rank_five_capstones():
    # Rank-5 capstone keys ('80'/'100') are reached at high mastery without error
    cultivator_laws = [
        {
            "mastery_percentage": 100.0,
            "mastery_effect": '{"20": {"damage_bonus": 0.15}, "80": {"execute_sub_20": true}, "100": {"sword_dominion": true}}',
        },
    ]
    effects = core_dl.resolve_law_effects(cultivator_laws)
    assert effects["damage_bonus"] == 0.15  # lower-rank effect still applied
    assert effects["unlocked_techniques"] == []  # capstones are flags, not techniques


def test_resolve_law_effects_respects_mastery_gate():
    cultivator_laws = [
        {
            "mastery_percentage": 10.0,
            "mastery_effect": '{"20": {"damage_bonus": 0.50}}',
        },
    ]
    effects = core_dl.resolve_law_effects(cultivator_laws)
    assert effects["damage_bonus"] == 0.0


def test_has_dao_fusion_requirement():
    laws_low = [{"mastery_percentage": 45.0}, {"mastery_percentage": 99.5}]
    assert not core_dl.has_dao_fusion_requirement(laws_low)

    laws_fusion_ready = [{"mastery_percentage": 45.0}, {"mastery_percentage": 100.0}]
    assert core_dl.has_dao_fusion_requirement(laws_fusion_ready)
