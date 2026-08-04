"""Pure logic tests for secret realms (core/secret_realms.py)."""
import random
from core import secret_realms as core_sr


def test_can_enter_realm_gate():
    realm = {"min_realm_tier": 3, "qi_cost": 200}

    # Low tier
    ok, err = core_sr.can_enter_realm(realm, {"realm_tier": 2, "qi_current": 500})
    assert not ok and "realm tier 3" in err

    # Low Qi
    ok, err = core_sr.can_enter_realm(realm, {"realm_tier": 3, "qi_current": 100})
    assert not ok and "Requires 200 Qi" in err

    # Ready
    ok, err = core_sr.can_enter_realm(realm, {"realm_tier": 4, "qi_current": 300})
    assert ok and err is None


def test_generate_node_encounter():
    enc_normal = core_sr.generate_node_encounter(realm_tier=2, node_index=1, total_nodes=3)
    assert enc_normal["node_index"] == 1
    assert not enc_normal["is_boss"]

    enc_boss = core_sr.generate_node_encounter(realm_tier=2, node_index=3, total_nodes=3)
    assert enc_boss["node_index"] == 3
    assert enc_boss["is_boss"]


def test_resolve_encounter_treasure():
    drop_table = [{"name": "Spirit Herb", "type": "Material", "grade": "Mortal", "weight": 100}]
    enc = {"type": "Treasure", "difficulty": 30}
    res = core_sr.resolve_encounter(enc, {"physique": 10, "spirit": 10}, choice="open", drop_table=drop_table)
    assert res["status"] == "success"
    assert res["loot"]["name"] == "Spirit Herb"


def test_resolve_encounter_evade():
    random.seed(42)
    enc = {"type": "Monster", "difficulty": 100}
    res = core_sr.resolve_encounter(enc, {"luck": 50}, choice="evade")
    assert res["status"] == "fled"
    assert res["qi_loss"] == 0


def test_resolve_encounter_monster_combat():
    random.seed(42)
    drop_table = [{"name": "Monster Core", "type": "Material", "grade": "Earth", "weight": 100}]
    enc = {"type": "Monster", "difficulty": 30}
    res = core_sr.resolve_encounter(enc, {"physique": 50, "spirit": 50}, choice="fight", drop_table=drop_table)
    assert res["status"] == "success"
    assert res["loot"]["name"] == "Monster Core"
