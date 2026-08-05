"""Pure logic tests for the Contendance combat engine (core/combat.py)."""
import random

from core import combat as cbt


def _intent(kind: str, **overrides) -> dict:
    base = {
        "kind": kind,
        "technique": None,
        "entries": [],
        "rank": 1,
        "law": None,
        "laws": {},
        "stats": {"physique": 10, "spirit": 10},
        "parry": 10,
    }
    base.update(overrides)
    return base


def _tech_intent(base_damage: int, law: str | None = None, entries: list[str] | None = None,
                 rank: int = 1, stats: dict | None = None, laws: dict | None = None) -> dict:
    return _intent(
        "technique",
        technique={"base_damage": base_damage, "stored_qi_cost": 10, "law_affinity": law},
        entries=entries or [],
        rank=rank,
        stats=stats or {"physique": 10, "spirit": 10},
        laws=laws or ({"Law of Space": 0.0} if law else {}),
    )


def _unfold_intent(name: str, mastery: float) -> dict:
    return _intent("unfold", law={"name": name, "rank": cbt_rank(mastery), "mastery": mastery})


def cbt_rank(mastery: float) -> int:
    return cbt.technique_rank(mastery)


# --------------------------------------------------------------------------- tables
def test_hp_table_is_complete_and_monotonic():
    assert len(cbt.HP_MAX) == 16
    prev = 0
    for tier in range(1, 17):
        assert cbt.HP_MAX[tier] > prev, f"HP must grow each realm ({tier})"
        prev = cbt.HP_MAX[tier]
    assert cbt.hp_max(1) == cbt.HP_MAX[1]


def test_technique_rank_curve():
    assert cbt.technique_rank(0) == 0
    assert cbt.technique_rank(19.9) == 0
    assert cbt.technique_rank(20.0) == 1
    assert cbt.technique_rank(100.0) == 5


def test_technique_damage_and_cost():
    tech = {"base_damage": 20, "stored_qi_cost": 30}
    stats = {"physique": 20, "spirit": 30}   # (20+30)//10 = 5
    assert cbt.technique_damage(tech, 1, stats) == 25
    assert cbt.technique_damage(tech, 3, stats) == 25 + 2 * cbt.TECHNIQUE_RANK_DAMAGE
    # Rank reduces cost, floored at TECHNIQUE_MIN_COST
    assert cbt.technique_cost(tech, 1) == 30
    assert cbt.technique_cost(tech, 4) == 30 - 3 * cbt.TECHNIQUE_RANK_COST_REDUCTION
    assert cbt.technique_cost(tech, 10) == cbt.TECHNIQUE_MIN_COST


def test_entry_modifiers():
    mods = cbt.entry_modifiers(["afterimage", "penetration", "overcharge", "karmic_weight"])
    assert mods["negate_damage"] == 15
    assert mods["penetration_ranks"] == 1
    assert mods["damage_mult"] == 2.0
    assert mods["karmic_scale"] == 5
    assert cbt.entry_modifiers([])["damage_mult"] == 1.0


def test_roll_entries_is_deterministic_with_seed():
    rng = random.Random(7)
    entries = cbt.roll_entries(rng)
    assert cbt.ENTRY_MIN_ROLL <= len(entries) <= cbt.ENTRY_MAX_ROLL
    assert len(set(entries)) == len(entries)  # unique
    pool = {e["key"] for e in cbt.ENTRY_POOL}
    assert set(entries) <= pool
    # Same seed -> same roll
    assert cbt.roll_entries(random.Random(7)) == entries


# --------------------------------------------------------------------------- clash resolution
def test_attack_vs_attack_higher_power_wins():
    a = _tech_intent(30)
    b = _tech_intent(20)
    outcome = cbt.resolve_round(a, b, d20_a=15, d20_b=15)
    # A power 30+15=45 vs B 20+15=35 -> A hits B, B's half-blow may land too
    assert outcome["damage_b"] > outcome["damage_a"]
    assert outcome["kind"] in ("clean_hit", "partial_block")


def test_mutual_negation_on_close_powers():
    a = _tech_intent(20)
    b = _tech_intent(20)
    outcome = cbt.resolve_round(a, b, d20_a=10, d20_b=11)  # diff 1
    assert outcome["kind"] == "mutual_negation"
    assert outcome["damage_a"] == 0 and outcome["damage_b"] == 0


def test_artifact_parry_halves_incoming():
    a = _tech_intent(40)
    b = _intent("artifact", parry=10)
    outcome = cbt.resolve_round(a, b, d20_a=10, d20_b=10)
    full = 40 + (20 // 10) + 10
    assert outcome["damage_b"] <= full // 2
    assert "parried" in outcome["notes"]


def test_unfold_counter_two_ranks_ahead():
    # Defender (B) unfolds Law of Space at 100% (rank 5); attacker (A) uses a
    # Space technique with rank 1 mastery (0-19%) -> 5 - 0 >= 2 -> counter
    a = _tech_intent(30, law="Law of Space", laws={"Law of Space": 10.0})
    b = _unfold_intent("Law of Space", 100.0)
    outcome = cbt.resolve_round(a, b, d20_a=10, d20_b=15)
    assert outcome["kind"] == "counter"
    assert outcome["damage_a"] > 0 and outcome["damage_b"] == 0


def test_law_resistance_reduces_damage():
    # Same attack, defender with vs without Space law mastery
    a = _tech_intent(40, law="Law of Space")
    no_res = _intent("pass", laws={})
    res = _intent("pass", laws={"Law of Space": 100.0})   # rank 5 -> 25% resist
    o1 = cbt.resolve_round(a, no_res, d20_a=5, d20_b=0)
    o2 = cbt.resolve_round(a, res, d20_a=5, d20_b=0)
    assert o2["damage_b"] < o1["damage_b"]
    assert "resisted" in o2["notes"]


def test_penetration_ignores_resistance():
    a_res = _tech_intent(40, law="Law of Space", laws={"Law of Space": 100.0})
    a_pen = _tech_intent(40, law="Law of Space", laws={"Law of Space": 100.0},
                         entries=["penetration"])
    defender = _intent("pass", laws={"Law of Space": 100.0})
    o_res = cbt.resolve_round(a_res, defender, d20_a=5, d20_b=0)
    o_pen = cbt.resolve_round(a_pen, defender, d20_a=5, d20_b=0)
    assert o_pen["damage_b"] > o_res["damage_b"]


def test_overcharge_doubles_damage():
    plain = _tech_intent(20)
    over = _tech_intent(20, entries=["overcharge"])
    o1 = cbt.resolve_round(plain, _intent("pass"), d20_a=0, d20_b=0)
    o2 = cbt.resolve_round(over, _intent("pass"), d20_a=0, d20_b=0)
    assert o2["damage_b"] >= o1["damage_b"] * 2 - 1


def test_retreat_ends_round():
    outcome = cbt.resolve_round(_tech_intent(30), _intent("retreat"), d20_a=10, d20_b=10)
    assert outcome["kind"] == "retreat"


def test_dao_heart_broken():
    assert cbt.dao_heart_broken(0) is True
    assert cbt.dao_heart_broken(-5) is True
    assert cbt.dao_heart_broken(1) is False


def test_can_burn():
    from core import math as gm
    assert cbt.can_burn(1000, 1) is True      # burn_cost(1) = 150
    assert cbt.can_burn(100, 1) is False
    assert gm.burn_cost(1) == 150


def test_duel_stall_cap_constant():
    """Duels must end — a stall (pill vs pill) resolves by HP at the cap."""
    assert cbt.MAX_DUEL_ROUNDS == 30


# --------------------------------------------------------------------------- beasts
def test_beast_catalog_is_valid():
    assert cbt.validate_beasts() == []


def test_beast_lookup_and_pattern():
    beast = cbt.beast_by_name("ancient sword spirit")
    assert beast is not None and beast["name"] == "Ancient Sword Spirit"
    assert cbt.beast_by_name("nope") is None
    # Patterns cycle
    assert cbt.beast_intent_for(beast, 0) == beast["intents"][0]
    assert cbt.beast_intent_for(beast, len(beast["intents"])) == beast["intents"][0]
