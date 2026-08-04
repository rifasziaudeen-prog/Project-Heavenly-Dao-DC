"""Pure logic unit tests for world events (core/world_events.py)."""
from core import world_events as core_we


def test_calculate_damage_base():
    stats = {"strength": 10, "spirit": 10}
    # Base = (10*8 + 10*4 + 0) = 120
    dmg = core_we.calculate_damage(stats, rng_factor=1.0)
    assert dmg == 120


def test_calculate_damage_with_weapon_and_multipliers():
    stats = {"strength": 20, "spirit": 15}
    # Base = (20*8 + 15*4 + 50) = 270
    # Mult = 1.5 (technique) * 1.2 (sect array) * (1 + 100/1000) = 1.5 * 1.2 * 1.1 = 1.98
    # Damage = 270 * 1.98 = 534.6 -> int(534)
    dmg = core_we.calculate_damage(
        stats,
        weapon_bonus=50,
        technique_mult=1.5,
        sect_array_bonus=1.2,
        law_mastery=100.0,
        rng_factor=1.0,
    )
    assert dmg == 534


def test_determine_boss_phase_transitions():
    p1, name1 = core_we.determine_boss_phase(900, 1000)
    assert p1 == 1 and "Normal" in name1

    p2, name2 = core_we.determine_boss_phase(700, 1000)
    assert p2 == 2 and "Enraged" in name2

    p3, name3 = core_we.determine_boss_phase(400, 1000)
    assert p3 == 3 and "Minions" in name3

    p4, name4 = core_we.determine_boss_phase(200, 1000)
    assert p4 == 4 and "Desperation" in name4

    p5, name5 = core_we.determine_boss_phase(50, 1000)
    assert p5 == 5 and "Final Stand" in name5


def test_calculate_sect_sacrifice_buff_tiers():
    buff0 = core_we.calculate_sect_sacrifice_buff(50)
    assert buff0["damage_buff"] == 0.0

    buff100 = core_we.calculate_sect_sacrifice_buff(100)
    assert buff100["damage_buff"] == 0.10 and not buff100["healing"]

    buff500 = core_we.calculate_sect_sacrifice_buff(500)
    assert buff500["damage_buff"] == 0.25 and buff500["healing"]

    buff1000 = core_we.calculate_sect_sacrifice_buff(1000)
    assert buff1000["damage_buff"] == 0.50 and buff1000["debuff_immunity"]


def test_calculate_event_rewards_ranking():
    participants = [
        {"cultivator_id": 1, "damage_dealt": 500},
        {"cultivator_id": 2, "damage_dealt": 10000},
        {"cultivator_id": 3, "damage_dealt": 3000},
        {"cultivator_id": 4, "damage_dealt": 1500},
    ]
    rewards = core_we.calculate_event_rewards(participants)

    # Rank 1 (ID 2)
    assert rewards[0]["cultivator_id"] == 2
    assert rewards[0]["rank"] == 1
    assert rewards[0]["item_grade"] == "God"
    assert rewards[0]["spirit_stones"] == 500

    # Rank 2 (ID 3)
    assert rewards[1]["cultivator_id"] == 3
    assert rewards[1]["rank"] == 2
    assert rewards[1]["item_grade"] == "Immortal"
    assert rewards[1]["spirit_stones"] == 300

    # Rank 3 (ID 4)
    assert rewards[2]["cultivator_id"] == 4
    assert rewards[2]["rank"] == 3
    assert rewards[2]["spirit_stones"] == 150

    # Rank 4 (ID 1)
    assert rewards[3]["cultivator_id"] == 1
    assert rewards[3]["rank"] == 4
    assert rewards[3]["spirit_stones"] == 50
