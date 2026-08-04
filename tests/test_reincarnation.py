"""Pure logic tests for the reincarnation engine (core/reincarnation.py)."""
from core import reincarnation as core_reinc


def test_can_voluntary_reincarnate_gate():
    c_tier4 = {"realm_tier": 4, "qi_current": 1000, "qi_capacity": 1000}
    ok, err = core_reinc.can_voluntary_reincarnate(c_tier4)
    assert not ok and "Nascent Soul" in err

    c_tier5_low_qi = {"realm_tier": 5, "qi_current": 100, "qi_capacity": 1000}
    ok, err = core_reinc.can_voluntary_reincarnate(c_tier5_low_qi)
    assert not ok and "half-full" in err

    c_tier5_ready = {"realm_tier": 5, "qi_current": 500, "qi_capacity": 1000}
    ok, err = core_reinc.can_voluntary_reincarnate(c_tier5_ready)
    assert ok and err is None


def test_get_physique_name():
    assert core_reinc.get_physique_name(0) == "Mortal Meridian"
    assert "Reincarnated Soul" in core_reinc.get_physique_name(1)
    assert "Twice-Born" in core_reinc.get_physique_name(2)
    assert "Heavenly Dao Reject" in core_reinc.get_physique_name(5)
    assert "Heavenly Dao Reject" in core_reinc.get_physique_name(10)


def test_calculate_legacy_and_rebirth_stats():
    cultivator = {
        "id": 1,
        "username": "Ling",
        "realm_tier": 6,
        "comprehension": 100,
        "luck": 50,
        "stat_points": 20,
        "reincarnation_cycle": 1,
        "inherited_technique": "Sword Intent",
    }
    legacy = core_reinc.calculate_legacy(cultivator)
    assert legacy["retained_stats"]["comprehension"] == 25  # 25% of 100
    assert legacy["retained_stats"]["luck"] == 5           # 10% of 50
    assert legacy["retained_stats"]["stat_points"] == 10    # 50% of 20
    assert legacy["cycle_bonus"]["breakthrough_bonus"] == 0.10  # (1 + 1)*5% = 10%

    base_stats = {"strength": 10, "spirit": 10, "physique": 10, "comprehension": 10, "luck": 5}
    new_stats = core_reinc.calculate_rebirth_stats(base_stats, legacy)
    # Comp = 10 (base) + 25 (retained) + 2 (cycle 1 bonus) = 37
    assert new_stats["comprehension"] == 37
    # Luck = 5 (base) + 5 (retained) = 10
    assert new_stats["luck"] == 10
    assert new_stats["stat_points"] == 10


def test_select_retained_technique():
    inventory = [
        {"name": "Pill", "item_type": "Pill", "is_equipped": 0},
        {"name": "Basic Manual", "item_type": "Technique_Scroll", "is_equipped": 0},
        {"name": "Immortal Scripture", "item_type": "Technique_Scroll", "is_equipped": 1},
    ]
    # Equipped scroll must be preferred
    chosen = core_reinc.select_retained_technique(inventory)
    assert chosen == "Immortal Scripture"

    # Fallback to unequipped scroll if no equipped scroll
    unequipped_inv = [
        {"name": "Basic Manual", "item_type": "Technique_Scroll", "is_equipped": 0},
    ]
    assert core_reinc.select_retained_technique(unequipped_inv) == "Basic Manual"

    # None if no scrolls
    assert core_reinc.select_retained_technique([]) is None


def test_generate_epitaph():
    c = {
        "username": "Xiao Chen",
        "realm_tier": 5,
        "realm_sub_stage": 2,
        "qi_current": 4000,
        "karma_points": 100,
        "reincarnation_cycle": 0,
        "gender": "male",
    }
    epitaph = core_reinc.generate_epitaph(c)
    assert "Xiao Chen" in epitaph
    assert "his" in epitaph


def test_unlock_memory_thresholds():
    c0 = {"reincarnation_cycle": 0, "comprehension": 1000}
    assert core_reinc.unlock_memory(c0) is None

    c1_100 = {"reincarnation_cycle": 1, "comprehension": 100}
    assert "Whispers from a past life" in core_reinc.unlock_memory(c1_100)

    c1_250 = {"reincarnation_cycle": 1, "comprehension": 250}
    assert "previous death" in core_reinc.unlock_memory(c1_250, existing_memories=["first_memory"])

    c1_1000 = {"reincarnation_cycle": 2, "comprehension": 1000}
    mem = core_reinc.unlock_memory(c1_1000, existing_memories=["first_memory", "death_memory", "technique_origin"])
    assert "ultimate truth" in mem


def test_execute_rebirth_payload():
    c = {
        "id": 42,
        "username": "Mo Fan",
        "realm_tier": 6,
        "realm_sub_stage": 4,
        "qi_current": 100000,
        "comprehension": 80,
        "luck": 40,
        "stat_points": 10,
        "reincarnation_cycle": 1,
    }
    updates, log = core_reinc.execute_rebirth_payload(c, reason="voluntary")

    assert updates["realm_tier"] == 1
    assert updates["reincarnation_cycle"] == 2
    assert "Twice-Born" in updates["cultivation_physique"]
    assert log["cultivator_id"] == 42
    assert log["cycle_from"] == 1
    assert log["cycle_to"] == 2
    assert log["reason"] == "voluntary"
