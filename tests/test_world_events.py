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


# ---------------------------------------------------------------------------
# World-boss Contendance (Part 5 · Commit 3) — scripted intent patterns
# ---------------------------------------------------------------------------

def test_boss_intent_pattern_cycles():
    assert core_we.boss_intent_for("demon_beast_siege", 0) == "unfold"
    assert core_we.boss_intent_for("demon_beast_siege", 1) == "technique"
    # Pattern wraps with the round index.
    assert core_we.boss_intent_for("demon_beast_siege", 6) == "unfold"
    assert core_we.boss_intent_for("sect_war", 4) == "unfold"
    # Unknown event type falls back to a plain technique pattern.
    assert core_we.boss_intent_for("unknown_type", 0) == "technique"


def test_build_boss_intent_shapes():
    tech = core_we.build_boss_intent("sect_war", 2, 1)
    assert tech["kind"] == "technique"
    assert tech["technique"]["base_damage"] == core_we.BOSS_PHASE_POWER[2]
    assert tech["law"] is None

    unfold = core_we.build_boss_intent("demon_beast_siege", 3, 0)
    assert unfold["kind"] == "unfold"
    assert unfold["law"]["name"] == "Law of Sword"
    assert unfold["law"]["rank"] == 1

    pas = core_we.build_boss_intent("ancient_ruin_awakening", 5, 0)
    assert pas["kind"] == "pass"


def test_boss_phase_power_table():
    assert set(core_we.BOSS_PHASE_POWER) == {1, 2, 3, 4, 5}
    powers = list(core_we.BOSS_PHASE_POWER.values())
    assert powers == sorted(powers) and len(set(powers)) == 5


def _player_intent(kind, laws=None, parry=0, stats=None):
    laws = laws or {}
    return {
        "kind": kind,
        "technique": {"base_damage": 8, "stored_qi_cost": 5, "law_affinity": None},
        "entries": [], "rank": 1,
        "law": {"name": "Law of Sword", "rank": 3, "mastery": 60.0} if kind == "unfold" else None,
        "laws": laws,
        "stats": stats or {"physique": 10, "spirit": 10},
        "parry": parry,
    }


def test_boss_exchange_counter_sword_law():
    # Player unfolds Law of Sword (rank 3, 2+ ahead of the boss's rank-1
    # unleash) on an unfold round -> deterministic counter, boss takes damage,
    # player takes none.
    player = _player_intent("unfold", laws={"Law of Sword": 60.0})
    res = core_we.resolve_boss_exchange(player, "demon_beast_siege", 1, 0,
                                        d20_player=5, d20_boss=10)
    assert res["kind"] == "counter"
    assert res["damage_to_boss"] > 0
    assert res["damage_to_player"] == 0


def test_boss_exchange_pass_round_is_free():
    # Round 0 of ancient_ruin_awakening is 'pass' -> free hit, no counterblow.
    player = _player_intent("technique")
    res = core_we.resolve_boss_exchange(player, "ancient_ruin_awakening", 2, 0,
                                        d20_player=5, d20_boss=5)
    assert res["boss_intent"] == "pass"
    assert res["damage_to_boss"] == core_we.BOSS_DAMAGE_SCALE * 15  # (8+2+5)*30
    assert res["damage_to_player"] == 0


def test_boss_exchange_artifact_parries_technique():
    bare = core_we.resolve_boss_exchange(
        _player_intent("technique"), "sect_war", 2, 1, d20_player=5, d20_boss=5)
    guarded = core_we.resolve_boss_exchange(
        _player_intent("artifact", parry=25), "sect_war", 2, 1, d20_player=5, d20_boss=5)
    # The guarded player eats at most half of the bare blow.
    assert "parried" in guarded["notes"]
    assert guarded["damage_to_player"] <= max(0, bare["damage_to_player"] // 2) + 1


def test_boss_exchange_pill_eats_the_blow():
    player = _player_intent("pill")
    res = core_we.resolve_boss_exchange(player, "sect_war", 2, 1, d20_player=5, d20_boss=5)
    assert res["damage_to_boss"] == 0
    assert res["damage_to_player"] > 0


def test_boss_exchange_damage_scale_constant():
    # Boss damage is flat-scaled off the engine's combat damage.
    player = _player_intent("technique")
    res = core_we.resolve_boss_exchange(player, "sect_war", 2, 1,
                                        d20_player=5, d20_boss=5)
    assert res["damage_to_boss"] % core_we.BOSS_DAMAGE_SCALE == 0
