"""Deterministic Contendance (争道) combat engine.

All combat math lives here as pure functions — no Discord or DB access — so
the whole system is unit-testable and every balance number is a named
constant in ONE file. The cog (cogs/combat.py) is thin glue: it feeds
round-intent dicts in, gets outcome dicts out, and narrates.

Intent shape (built by the cog from player choices + DB data):
    {
      "kind": "technique" | "unfold" | "artifact" | "pill" | "retreat" | "pass",
      "technique": {"base_damage": int, "stored_qi_cost": int,
                    "law_affinity": str | None} | None,
      "entries": [str, ...],            # entry keys rolled on the technique
      "rank": int,                      # technique mastery rank 1-5
      "law": {"name": str, "rank": int} | None,   # unfolded law (kind='unfold')
      "laws": {law_name: mastery},      # ALL law masteries (for resistance)
      "stats": {"physique": int, "spirit": int},
      "parry": int,                     # artifact parry value (kind='artifact')
    }

Round outcome dict (from resolve_round):
    kind         clean_hit | partial_block | mutual_negation | counter | retreat | pass
    damage_a     HP lost by side A (defender of b's attack)
    damage_b     HP lost by side B
    dao_heart_a  Dao Heart lost by A
    dao_heart_b  Dao Heart lost by B
    notes        list[str] — narrative tokens (e.g. 'resisted', 'parried', 'countered')
"""
from __future__ import annotations

import random

from core import dao_laws as core_dl

# ---------------------------------------------------------------------------
# HP — flat per-realm table (tunable: this dict is the only knob)
# ---------------------------------------------------------------------------
HP_MAX: dict[int, int] = {
    1: 120, 2: 150, 3: 190, 4: 240, 5: 300, 6: 370, 7: 450, 8: 540,
    9: 650, 10: 780, 11: 930, 12: 1_100, 13: 1_300, 14: 1_550,
    15: 1_850, 16: 2_200,
}

DAO_HEART_MAX = 100          # flat mental-fortitude pool, resets each fight
DAO_HEART_LOSS_PER_CLASH = 10  # losing an exchange chips the mind
DAO_HEART_MIN = 0

# ---------------------------------------------------------------------------
# Technique quality tiers (White -> Red)
# ---------------------------------------------------------------------------
QUALITY_META: dict[str, dict] = {
    "White":  {"emoji": "⬜", "color": "light_grey"},
    "Green":  {"emoji": "🟩", "color": "green"},
    "Blue":   {"emoji": "🟦", "color": "blue"},
    "Purple": {"emoji": "🟪", "color": "purple"},
    "Orange": {"emoji": "🟧", "color": "orange"},
    "Red":    {"emoji": "🟥", "color": "red"},
}

# Mastery curve mirrors the law ranks: rank up at 20/40/60/80/100 progress.
TECHNIQUE_RANK_THRESHOLDS = (20, 40, 60, 80, 100)
TECHNIQUE_MASTERY_PER_USE = 2        # +2 progress per clash use
TECHNIQUE_RANK_DAMAGE = 3            # +3 damage per rank above 1
TECHNIQUE_RANK_COST_REDUCTION = 5    # -5 Stored Qi per rank above 1
TECHNIQUE_MIN_COST = 5

# Intent action costs (Stored Qi)
LAW_UNFOLD_COST = 30
ARTIFACT_COST = 10

# Round pacing (user approved 20s; tune here)
INTENT_WINDOW_SECONDS = 20
MAX_DUEL_ROUNDS = 30      # hard cap per duel — a stall (pill vs pill) ends by HP

# Artifact parry base + cap (equipped weapon stat buffs add on top)
ARTIFACT_PARRY_BASE = 10
ARTIFACT_PARRY_CAP = 40

# Burn (overdraft) conversion — flat, no percentages
BURN_STORED_QI_GAIN = 100            # burning the base grants +100 Stored Qi
BURN_DAO_HEART_COST = 10             # ... and chips the mind

# ---------------------------------------------------------------------------
# Technique entries — deterministic modifiers (tunable; user may re-tune later)
# ---------------------------------------------------------------------------
ENTRY_POOL: list[dict] = [
    {"key": "afterimage", "name": "Afterimage 残影",
     "desc": "Negates 15 incoming damage this clash",
     "effect": {"negate_damage": 15}},
    {"key": "penetration", "name": "Penetration 破防",
     "desc": "Ignores 1 rank of the target's law resistance",
     "effect": {"penetration_ranks": 1}},
    {"key": "overcharge", "name": "Overcharge 蓄势",
     "desc": "Doubles damage, doubles Stored Qi cost",
     "effect": {"damage_mult": 2.0, "cost_mult": 2.0}},
    {"key": "karmic_weight", "name": "Karmic Weight 业火",
     "desc": "+5 damage per 1,000 negative karma the opponent carries",
     "effect": {"karmic_scale": 5}},
]
ENTRY_MIN_ROLL = 1
ENTRY_MAX_ROLL = 3

# --------------------------------------------------------------------------- helpers
def hp_max(realm_tier: int) -> int:
    return HP_MAX.get(realm_tier, HP_MAX[1])


def technique_rank(mastery_progress: float) -> int:
    """Rank 0-5 from mastery progress (same curve as laws)."""
    rank = 0
    for threshold in TECHNIQUE_RANK_THRESHOLDS:
        if mastery_progress >= threshold:
            rank += 1
    return rank


def technique_damage(tech: dict, rank: int, stats: dict) -> int:
    """Base damage + stat scaling + rank bonus (flat, no percentages)."""
    stat_part = (int(stats.get("physique", 10)) + int(stats.get("spirit", 10))) // 10
    return int(tech.get("base_damage", 8)) + stat_part + max(0, rank - 1) * TECHNIQUE_RANK_DAMAGE


def technique_cost(tech: dict, rank: int) -> int:
    """Stored Qi cost with rank reduction (flat, floor at TECHNIQUE_MIN_COST)."""
    cost = int(tech.get("stored_qi_cost", 10)) - max(0, rank - 1) * TECHNIQUE_RANK_COST_REDUCTION
    return max(TECHNIQUE_MIN_COST, cost)


def entry_modifiers(entries: list[str]) -> dict:
    """Aggregate deterministic entry effects into one modifier dict."""
    mods = {"negate_damage": 0, "penetration_ranks": 0, "damage_mult": 1.0, "cost_mult": 1.0, "karmic_scale": 0}
    for key in entries:
        for entry in ENTRY_POOL:
            if entry["key"] == key:
                eff = entry["effect"]
                for field in mods:
                    if field in eff:
                        if isinstance(eff[field], float):
                            mods[field] *= eff[field]
                        else:
                            mods[field] += eff[field]
                break
    return mods


def roll_entries(rng: random.Random | None = None) -> list[str]:
    """Roll 1-3 unique entry keys at learn time (deterministic with seeded rng)."""
    rng = rng or random
    count = rng.randint(ENTRY_MIN_ROLL, ENTRY_MAX_ROLL)
    keys = [e["key"] for e in ENTRY_POOL]
    rng.shuffle(keys)
    return sorted(keys[:count])


def entry_labels(entries: list[str]) -> list[str]:
    return [f"{e['name']} ({e['desc']})" for e in ENTRY_POOL if e["key"] in entries]


# --------------------------------------------------------------------------- clash math
def _resistance_for(laws: dict, law_name: str | None) -> float:
    """Defender's damage reduction vs an incoming law (5% per rank)."""
    if not law_name:
        return 0.0
    mastery = float(laws.get(law_name, 0.0))
    return core_dl.law_resistance(mastery)


def _attack_power(intent: dict, d20: int) -> dict:
    """Offensive numbers for an intent (0 attack for non-offensive kinds)."""
    kind = intent["kind"]
    mods = entry_modifiers(intent.get("entries", []))
    stats = intent.get("stats", {})
    law_name = None

    if kind == "technique":
        tech = intent.get("technique") or {}
        rank = int(intent.get("rank", 1))
        base = technique_damage(tech, rank, stats) + d20
        base = int(base * mods["damage_mult"])
        law_name = tech.get("law_affinity")
        return {"power": base, "damage": base, "law": law_name, "mods": mods, "mental": False}

    if kind == "unfold":
        law = intent.get("law") or {}
        rank = int(law.get("rank", 1))
        base = 10 + rank * 4 + (int(stats.get("physique", 10)) + int(stats.get("spirit", 10))) // 20 + d20
        law_name = law.get("name")
        return {"power": base, "damage": base, "law": law_name, "mods": mods, "mental": False}

    # Artifact with a charged active ability strikes as well as parries.
    if kind == "artifact":
        active = int(intent.get("active_power", 0))
        if active > 0:
            return {"power": active, "damage": active, "law": None, "mods": mods, "mental": False}
        return {"power": 0, "damage": 0, "law": None, "mods": mods, "mental": False}

    # pill / retreat / pass — non-offensive
    return {"power": 0, "damage": 0, "law": None, "mods": mods, "mental": False}


def _defense_value(intent: dict) -> int:
    kind = intent["kind"]
    if kind == "artifact":
        return int(intent.get("parry", 10))
    if kind == "unfold":
        rank = int((intent.get("law") or {}).get("rank", 1))
        return 5 + rank * 5
    return 0


def _counter_power(counter_intent: dict, d20: int) -> int:
    """The counter strike uses the unfold's power."""
    return _attack_power(counter_intent, d20)["power"]


def resolve_round(a: dict, b: dict, d20_a: int = 0, d20_b: int = 0) -> dict:
    """Resolve one Contendance round (pure, deterministic given the d20s).

    Side A attacks side B. Outcomes:
      clean_hit        — attacker's blow lands (higher power, or defender passive)
      partial_block    — defender's active defense (artifact/unfold) blunts it
      mutual_negation  — both attacked, powers within 3 -> both miss
      counter          — defender unfolded the same law 2+ ranks ahead
      retreat / pass   — no exchange
    """
    if a.get("kind") == "retreat" or b.get("kind") == "retreat":
        return {"kind": "retreat", "damage_a": 0, "damage_b": 0,
                "dao_heart_a": 0, "dao_heart_b": 0, "notes": ["retreated"]}

    a_atk = _attack_power(a, d20_a)
    b_atk = _attack_power(b, d20_b)
    a_def = _defense_value(a)
    b_def = _defense_value(b)

    notes: list[str] = []
    damage_a = 0   # HP lost by A
    damage_b = 0   # HP lost by B
    dh_a = 0
    dh_b = 0

    # --- B's counter (B unfolded the same law A attacked with, 2+ ranks ahead)
    if b.get("kind") == "unfold" and a_atk["law"] and (b.get("law") or {}).get("name") == a_atk["law"]:
        b_law = b.get("law") or {}
        a_law_rank = core_dl.law_rank(float((a.get("laws") or {}).get(a_atk["law"], 0.0)))
        if int(b_law.get("rank", 0)) - a_law_rank >= 2:
            damage_a = _counter_power(b, d20_b)
            damage_a = max(0, damage_a - a_atk["mods"].get("negate_damage", 0))
            dh_a = DAO_HEART_LOSS_PER_CLASH
            notes.append("countered")
            return {"kind": "counter", "damage_a": damage_a, "damage_b": 0,
                    "dao_heart_a": dh_a, "dao_heart_b": 0, "notes": notes}

    # --- A attacks B
    if a_atk["power"] > 0 and b_atk["power"] > 0:
        # Both attacked: mutual negation within 3 power, else both connect
        if abs(a_atk["power"] - b_atk["power"]) <= 3:
            return {"kind": "mutual_negation", "damage_a": 0, "damage_b": 0,
                    "dao_heart_a": 0, "dao_heart_b": 0, "notes": ["clashed"]}
        a_hit, b_hit = (a_atk["power"] > b_atk["power"]), (b_atk["power"] > a_atk["power"])
    else:
        a_hit, b_hit = a_atk["power"] > 0, b_atk["power"] > 0

    # Damage A deals to B
    if a_hit:
        res = max(0.0, _resistance_for(b.get("laws", {}), a_atk["law"]) - a_atk["mods"].get("penetration_ranks", 0) * 0.05)
        raw = a_atk["damage"]
        if b.get("kind") == "artifact":
            raw //= 2
            notes.append("parried")
        if b.get("kind") in ("artifact", "unfold") and b_def > 0 and a_atk["power"] <= b_def:
            raw //= 2
            notes.append("blocked")
        damage_b = max(0, int(raw * (1.0 - res)) - a_atk["mods"].get("negate_damage", 0))
        dh_b = DAO_HEART_LOSS_PER_CLASH
        notes.append("resisted" if res > 0 else "clean_hit")

    # Damage B deals to A
    if b_hit:
        res = max(0.0, _resistance_for(a.get("laws", {}), b_atk["law"]) - b_atk["mods"].get("penetration_ranks", 0) * 0.05)
        raw = b_atk["damage"]
        if a.get("kind") == "artifact":
            raw //= 2
        if a.get("kind") in ("artifact", "unfold") and a_def > 0 and b_atk["power"] <= a_def:
            raw //= 2
        damage_a = max(0, int(raw * (1.0 - res)) - b_atk["mods"].get("negate_damage", 0))
        dh_a = DAO_HEART_LOSS_PER_CLASH
        if res > 0:
            notes.append("resisted_b")

    kind = "clean_hit" if (a_hit or b_hit) else "mutual_negation"
    if "parried" in notes or "blocked" in notes:
        kind = "partial_block"
    return {"kind": kind, "damage_a": damage_a, "damage_b": damage_b,
            "dao_heart_a": dh_a, "dao_heart_b": dh_b, "notes": notes}


def dao_heart_broken(dao_heart: int) -> bool:
    """Dao Heart at/below zero -> the mind shatters (forced retreat)."""
    return dao_heart <= DAO_HEART_MIN


# --------------------------------------------------------------------------- burn (overdraft)
def can_burn(qi_current: int, realm_tier: int) -> bool:
    """A cultivator may burn their base only if they have enough dantian Qi."""
    from core import math as gm
    return qi_current >= gm.burn_cost(realm_tier)


# --------------------------------------------------------------------------- scripted PvE beasts
SCRIPTED_BEASTS: list[dict] = [
    {
        "name": "Stone-Arm Ape",
        "name_zh": "石臂猿",
        "realm_tier": 2,
        "hp": 90,
        "intents": ["technique", "unfold", "technique", "pass", "technique", "unfold"],
        "stones_reward": 25,
        "tech_drop_chance": 0.15,
    },
    {
        "name": "Azure Wind Wolf",
        "name_zh": "青风狼",
        "realm_tier": 4,
        "hp": 200,
        "intents": ["unfold", "technique", "technique", "unfold", "technique"],
        "stones_reward": 60,
        "tech_drop_chance": 0.25,
    },
    {
        "name": "Ancient Sword Spirit",
        "name_zh": "上古剑灵",
        "realm_tier": 7,
        "hp": 420,
        "intents": ["technique", "technique", "unfold", "technique", "technique", "unfold", "unfold"],
        "stones_reward": 180,
        "tech_drop_chance": 0.40,
    },
    {
        "name": "Thunderclap Serpent",
        "name_zh": "雷鸣巨蟒",
        "realm_tier": 10,
        "hp": 900,
        "intents": ["technique", "unfold", "technique", "technique", "unfold", "technique"],
        "stones_reward": 500,
        "tech_drop_chance": 0.55,
    },
]


def beast_by_name(name: str) -> dict | None:
    for beast in SCRIPTED_BEASTS:
        if beast["name"].lower() == name.strip().lower():
            return beast
    return None


def beast_intent_for(beast: dict, round_index: int) -> str:
    pattern = beast.get("intents", ["technique"])
    return pattern[round_index % len(pattern)]


def validate_beasts() -> list[str]:
    """Layout-style validator: every beast must have sane fields."""
    errors = []
    names = [b["name"] for b in SCRIPTED_BEASTS]
    if len(names) != len(set(names)):
        errors.append("SCRIPTED_BEASTS contains duplicate names")
    for b in SCRIPTED_BEASTS:
        for field in ("name", "name_zh", "realm_tier", "hp", "intents", "stones_reward", "tech_drop_chance"):
            if field not in b:
                errors.append(f"Beast {b.get('name', '?')!r} missing {field!r}")
        if not (1 <= b.get("realm_tier", 1) <= 16):
            errors.append(f"Beast {b.get('name')!r} realm_tier out of range")
        if b.get("hp", 0) <= 0:
            errors.append(f"Beast {b.get('name')!r} hp must be positive")
        if not b.get("intents"):
            errors.append(f"Beast {b.get('name')!r} needs an intent pattern")
    return errors
