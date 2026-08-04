"""Deterministic secret realms engine.

Pure Python logic for dungeon node encounters, stat-based checks,
and loot generation — no Discord or DB dependencies.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

ENCOUNTER_TYPES = ["Monster", "Treasure", "Trap", "Herb_Garden"]


def can_enter_realm(realm_template: Dict[str, Any], cultivator: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if cultivator meets realm tier and Qi cost requirements."""
    req_tier = realm_template.get("min_realm_tier", 1)
    qi_cost = realm_template.get("qi_cost", 50)

    if cultivator.get("realm_tier", 1) < req_tier:
        return False, f"Requires realm tier {req_tier} or higher to enter."

    if cultivator.get("qi_current", 0) < qi_cost:
        return False, f"Requires {qi_cost} Qi to open the secret realm portal. You have {cultivator.get('qi_current', 0)}."

    return True, None


def generate_node_encounter(realm_tier: int, node_index: int, total_nodes: int) -> Dict[str, Any]:
    """Generate deterministic or randomized node encounter based on depth."""
    if node_index == total_nodes:
        # Final node is always a Boss Monster or Ancient Treasury
        enc_type = random.choice(["Monster", "Treasure"])
        difficulty = 50 + realm_tier * 15 + node_index * 10
        is_boss = True
    else:
        enc_type = random.choice(ENCOUNTER_TYPES)
        difficulty = 30 + realm_tier * 10 + node_index * 5
        is_boss = False

    return {
        "node_index": node_index,
        "total_nodes": total_nodes,
        "type": enc_type,
        "difficulty": difficulty,
        "is_boss": is_boss,
        "title": f"Node {node_index}/{total_nodes}: Ancient {enc_type.replace('_', ' ')}" + (" (Guardian Boss!)" if is_boss else ""),
    }


def _select_random_loot(drop_table: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Weighted random loot selection from drop table."""
    if not drop_table:
        return {"name": "Spirit Herb", "type": "Material", "grade": "Mortal", "quantity": 1}

    weights = [item.get("weight", 10) for item in drop_table]
    selected = random.choices(drop_table, weights=weights, k=1)[0]
    return {
        "name": selected["name"],
        "type": selected.get("type", "Material"),
        "grade": selected.get("grade", "Mortal"),
        "quantity": selected.get("quantity", 1),
    }


def resolve_encounter(
    encounter: Dict[str, Any],
    cultivator_stats: Dict[str, int],
    choice: str,
    drop_table: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Resolve player choice against encounter node difficulty using stat checks.

    Returns:
      {
        "status": "success" | "failure" | "fled",
        "message": str,
        "loot": dict | None,
        "qi_loss": int,
        "heart_demon_delta": float,
      }
    """
    enc_type = encounter["type"]
    difficulty = encounter["difficulty"]
    choice_lower = choice.lower().strip()

    if choice_lower == "evade" or choice_lower == "flee":
        # Evade check vs Luck stat
        luck_roll = random.randint(1, 20) + cultivator_stats.get("luck", 5)
        if luck_roll >= 15:
            return {"status": "fled", "message": "You slipped past the danger unnoticed!", "loot": None, "qi_loss": 0, "heart_demon_delta": 0.0}
        else:
            return {"status": "failure", "message": "Evade failed! You triggered the trap while fleeing.", "loot": None, "qi_loss": 30, "heart_demon_delta": 0.01}

    if enc_type == "Monster":
        combat_stat = cultivator_stats.get("physique", 10) + cultivator_stats.get("spirit", 10)
        roll = random.gauss(mu=combat_stat, sigma=max(1.0, combat_stat * 0.2))
        if roll >= difficulty:
            loot = _select_random_loot(drop_table)
            return {"status": "success", "message": f"Slew the monster cleanly! Found **{loot['name']}**.", "loot": loot, "qi_loss": 0, "heart_demon_delta": 0.0}
        else:
            return {"status": "failure", "message": "Overpowered by the spirit beast!", "loot": None, "qi_loss": 50, "heart_demon_delta": 0.02}

    elif enc_type == "Treasure":
        loot = _select_random_loot(drop_table)
        return {"status": "success", "message": f"Opened the ancient chest! Obtained **{loot['name']}**.", "loot": loot, "qi_loss": 0, "heart_demon_delta": 0.0}

    elif enc_type == "Trap":
        luck_stat = cultivator_stats.get("luck", 5)
        roll = random.randint(1, 20) + luck_stat
        if roll >= 12:
            loot = _select_random_loot(drop_table)
            return {"status": "success", "message": f"Disarmed ancient formation! Salvaged **{loot['name']}**.", "loot": loot, "qi_loss": 0, "heart_demon_delta": 0.0}
        else:
            return {"status": "failure", "message": "Triggered poison dart trap!", "loot": None, "qi_loss": 40, "heart_demon_delta": 0.02}

    elif enc_type == "Herb_Garden":
        comp_stat = cultivator_stats.get("comprehension", 10)
        if comp_stat >= 15:
            loot = _select_random_loot(drop_table)
            return {"status": "success", "message": f"Harvested rare spiritual plants! Obtained **{loot['name']}**.", "loot": loot, "qi_loss": 0, "heart_demon_delta": 0.0}
        else:
            return {"status": "success", "message": "Harvested basic herbs.", "loot": {"name": "Spirit Herb", "type": "Material", "grade": "Mortal", "quantity": 1}, "qi_loss": 0, "heart_demon_delta": 0.0}

    return {"status": "success", "message": "Explored node safely.", "loot": None, "qi_loss": 0, "heart_demon_delta": 0.0}
