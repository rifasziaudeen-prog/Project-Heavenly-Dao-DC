"""Tests for the deterministic balance math (core/math.py)."""
import math

from core import math as gm

BASE_STATS = {"physique": 10, "spirit": 10, "luck": 5, "comprehension": 10}


def test_breakthrough_probability_bounds():
    for tier in range(1, 17):
        for layer in range(1, 10):
            p = gm.calculate_breakthrough_probability(BASE_STATS, tier, layer)
            assert 0.05 <= p <= 0.95, f"tier {tier} layer {layer}: {p}"


def test_breakthrough_harder_at_higher_tiers():
    p1 = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4)
    p8 = gm.calculate_breakthrough_probability(BASE_STATS, 8, 4)
    assert p8 < p1


def test_heart_demon_penalty():
    clean = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, heart_demon_ratio=0.0)
    plagued = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, heart_demon_ratio=0.5)
    assert plagued < clean


def test_karma_penalty_and_bonus_capped():
    low = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, karma_points=-50000)
    high = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, karma_points=50000)
    assert high - low <= 0.2 + 1e-9  # ±10% total


def test_dao_mercy_capped_at_25pct():
    base = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, failure_streak=0)
    maxed = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, failure_streak=100)
    assert maxed - base <= 0.25 + 1e-9


def test_qi_message_is_10pct_of_cultivate():
    msg = gm.calculate_qi_gain(1, 10, source="message")
    cult = gm.calculate_qi_gain(1, 10, source="cultivate")
    assert msg == int(cult * 0.10)


def test_qi_diminishing_returns_on_comprehension():
    low = gm.calculate_qi_gain(1, 10, source="cultivate")
    high = gm.calculate_qi_gain(1, 500, source="cultivate")
    # The old formula gave 6x at 500 comp; the new one must be far below that.
    assert high / low < 3.5


def test_qi_companion_bonus_capped_at_2x():
    companions = [{"intimacy_level": 10} for _ in range(30)]
    gain = gm.calculate_qi_gain(
        1, 10, source="cultivate", active_companions=companions
    )
    comp_bonus = 1.0 + math.log10(1.0 + 10 / 10.0)
    assert gain <= int(8 * comp_bonus * 2.0) + 1


def test_next_realm_step():
    assert gm.next_realm_step(1, 9) == (2, 1, True)
    assert gm.next_realm_step(2, 1) == (2, 2, False)
    # Summit cap: Beyond Dao (16/9) never regresses layers
    assert gm.next_realm_step(16, 9) == (16, 9, False)
    assert gm.next_realm_step(16, 8) == (16, 9, False)


def test_erasure_resolution():
    r = gm.resolve_erasure(None)
    assert r["erased"] is True and r["keep_stats"] == "partial"
    assert r["title"] == "Ashen Remnant"

    r = gm.resolve_erasure("karmic_shield")
    assert r["erased"] is False and r["title"] == "Heavenly Dao Resisted"

    r = gm.resolve_erasure("reincarnation_seed")
    assert r["erased"] is True and r["keep_stats"] == "full"

    r = gm.resolve_erasure("dao_heart_anchor")
    assert r["erased"] is False and r["qi_refund"] == 1.0 and r["heart_demon_delta"] < 0


def test_erasure_stat_retention():
    stats = {"physique": 10, "spirit": 10, "luck": 20, "comprehension": 40}
    kept = gm.apply_erasure_to_stats(stats, "partial")
    assert kept["comprehension"] == max(10, int(40 * 0.25))
    assert kept["luck"] == max(5, int(20 * 0.10))
    full = gm.apply_erasure_to_stats(stats, "full")
    assert full == stats


def test_rage_bonus_increases_probability():
    base = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4)
    raged = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, rage_bonus=0.15)
    assert raged >= base + 0.149
    assert raged <= 0.95
    # Negative rage (shouldn't happen) is clamped away
    calm = gm.calculate_breakthrough_probability(BASE_STATS, 1, 4, rage_bonus=-1.0)
    assert calm == base


def test_realm_ladder_is_16_by_9():
    assert gm.MAX_TIER == 16
    assert gm.MAX_LAYER == 9
    assert len(gm.REALMS) == 16
    assert len(gm.LAYERS) == 9
    # Names follow the Next Steps blueprint (Void Refinement inserted at 7)
    assert gm.REALMS[7] == ("Void Refinement", "炼虚")
    assert gm.REALMS[8] == ("Dao Fusion", "合体")
    assert gm.REALMS[9] == ("Tribulation Transcendence", "渡劫")
    assert gm.REALMS[10] == ("True Immortal", "真仙")
    assert gm.REALMS[16] == ("Beyond Dao", "超脱")


def test_qi_gain_flat_bonus_is_additive():
    base = gm.calculate_qi_gain(1, 10, source="cultivate")
    boosted = gm.calculate_qi_gain(1, 10, source="cultivate", flat_bonus=100)
    assert boosted == base + 100


def test_transcendence_payload_resets_and_grants():
    cultivator = {
        "transcendence_count": 0, "legacy_passives": "[]",
        "transcendence_capacity_bonus": 0, "transcendence_qi_gain_bonus": 0,
        "strength": 10, "spirit": 10, "physique": 10,
        "comprehension": 10, "luck": 5, "heart_demon_ratio": 0.5,
        "failure_streak": 4,
    }
    payload = gm.transcendence_payload(cultivator)
    # Active attributes reset
    assert payload["realm_tier"] == 1 and payload["realm_sub_stage"] == 1
    assert payload["qi_current"] == 0
    assert payload["heart_demon_ratio"] == 0.0
    assert payload["failure_streak"] == 0
    # Permanent flat gifts stack
    assert payload["strength"] == 10 + gm.TRANSCENDENCE_STAT_BONUS
    assert payload["luck"] == 5 + gm.TRANSCENDENCE_STAT_BONUS
    assert payload["transcendence_count"] == 1
    assert payload["transcendence_capacity_bonus"] >= gm.TRANSCENDENCE_QI_CAPACITY_BONUS
    assert payload["qi_capacity"] == gm.TRANSCENDENCE_BASE_CAPACITY + payload["transcendence_capacity_bonus"]
    # First passive is boundless_dantian (flat Qi gain)
    assert "boundless_dantian" in payload["legacy_passives"]
    assert payload["transcendence_qi_gain_bonus"] == 100


def test_transcendence_passives_cycle_and_stack():
    cultivator = {
        "transcendence_count": 1, "legacy_passives": "[\"boundless_dantian\"]",
        "transcendence_capacity_bonus": 15_000, "transcendence_qi_gain_bonus": 100,
        "strength": 25, "spirit": 25, "physique": 25,
        "comprehension": 25, "luck": 20, "heart_demon_ratio": 0.0,
        "failure_streak": 0,
    }
    payload = gm.transcendence_payload(cultivator)
    assert payload["transcendence_count"] == 2
    assert payload["strength"] == 25 + gm.TRANSCENDENCE_STAT_BONUS  # second passive = Immortal Vessel
    assert payload["transcendence_capacity_bonus"] == 15_000 + 5_000 + 10_000
    assert payload["transcendence_qi_gain_bonus"] == 100  # unchanged this cycle
    # 7th transcendence cycles back to boundless_dantian
    assert gm.next_legacy_passive(7)["key"] == "boundless_dantian"
    assert gm.next_legacy_passive(1)["key"] == "boundless_dantian"
    assert gm.next_legacy_passive(6)["key"] == "transcendent_physique"


def test_transcendence_titles():
    assert gm.transcendence_title(1) == "Transcendent I"
    assert gm.transcendence_title(2) == "Transcendent II"
    assert gm.transcendence_title(10) == "Transcendent X"
    assert gm.transcendence_title(11) == "Transcendent 11"


def test_erasure_only_rolls_tier_8_plus():
    assert gm.erasure_should_roll(7, True) is False
    assert gm.erasure_should_roll(8, True) is True
    assert gm.erasure_should_roll(8, False) is False


def test_language_formatting():
    from bot import utils as ui

    # realm_label
    assert gm.realm_label(3, 2, "bilingual") == "Foundation Establishment (2nd Layer) · 筑基二层"
    assert gm.realm_label(3, 2, "english") == "Foundation Establishment (2nd Layer)"

    # format_qi
    assert ui.format_qi(1000, "bilingual") == "1,000 灵力"
    assert ui.format_qi(1000, "english") == "1,000 Qi"

    # format_title
    assert ui.format_title("☯ Dao Awakening · 觉醒", "bilingual") == "☯ Dao Awakening · 觉醒"
    assert ui.format_title("☯ Dao Awakening · 觉醒", "english") == "☯ Dao Awakening"

