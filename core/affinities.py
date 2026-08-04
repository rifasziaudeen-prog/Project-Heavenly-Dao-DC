"""core/affinities.py

Spiritual Aptitude & Martial Intent Engine for the Heavenly Dao Engine (v1.1.0).

Defines:
  - AptitudeProfile      — dataclass holding all 12 aptitude values for a cultivator
  - generate_initial_aptitudes() — randomised awakening roll (pool-based, with Chaos Root chance)
  - clamp_aptitude() / add_aptitude_exp() — growth helpers
  - aptitude_stat_multipliers() — returns a dict of combat/cultivation modifiers
  - ELEMENT_META / INTENT_META — display metadata (emoji, name, effect description)

Design rules:
  * 60-point pool distributed randomly across 6 elemental aptitudes; single-stat max = 25.
  * 30-point pool distributed randomly across 4 martial intents; single-stat max = 15.
  * 1% chance of "Chaos Five-Element Root": all elemental aptitudes set to 20–25, balanced.
  * All aptitudes are clamped: elemental/intent values 0–100, yin_yang_balance -100..+100.
  * The `special_root` field is designed to support future root types (just add more strings).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELEMENT_POOL = 60          # total points across 6 elements on awakening
ELEMENT_MAX_SINGLE = 25    # no single element may exceed this on roll
ELEMENT_KEYS = ("affinity_fire", "affinity_water", "affinity_wood",
                "affinity_metal", "affinity_earth", "affinity_qi")
ELEMENT_COUNT = len(ELEMENT_KEYS)

INTENT_POOL = 30           # total points across 4 intents on awakening
INTENT_MAX_SINGLE = 15
INTENT_KEYS = ("intent_sword", "intent_sabre", "intent_spear", "intent_fist")
INTENT_COUNT = len(INTENT_KEYS)

CHAOS_ROOT_CHANCE = 0.01   # 1% — Chaos Five-Element balanced awakening
CHAOS_ROOT_TAG = "chaos"

# Display metadata — emojis and short combat descriptions for embeds
ELEMENT_META: dict[str, dict] = {
    "affinity_fire": {
        "emoji": "🔥", "name": "Fire",
        "effects": "+Crit Chance & Crit Multiplier, Fire Manual compatibility",
    },
    "affinity_water": {
        "emoji": "💧", "name": "Water",
        "effects": "+Evasion, +Speed, +Vitality Recovery, Water Manual compatibility",
    },
    "affinity_wood": {
        "emoji": "🪵", "name": "Wood",
        "effects": "+Toxin/Debuff Immunity, Wood Manual compatibility",
    },
    "affinity_metal": {
        "emoji": "🪙", "name": "Metal",
        "effects": "+Armor Penetration & Raw Damage, Metal Manual compatibility",
    },
    "affinity_earth": {
        "emoji": "🪨", "name": "Earth",
        "effects": "+CC Resistance & Barrier Shielding, Earth Manual compatibility",
    },
    "affinity_qi": {
        "emoji": "✨", "name": "Qi",
        "effects": "+Qi Regen Speed, +Qi Gain, +Dantian Efficiency",
    },
}

INTENT_META: dict[str, dict] = {
    "intent_sword": {
        "emoji": "🗡️", "name": "Sword Intent",
        "effects": "Multi-hit Trigger Chance & Phantom Evasion",
    },
    "intent_sabre": {
        "emoji": "🪓", "name": "Sabre Intent",
        "effects": "Sweeping Cleave Damage & Lifesteal Bloodlust",
    },
    "intent_spear": {
        "emoji": "🔱", "name": "Spear Intent",
        "effects": "Reach Counter-Attacks & Stance Armor Break",
    },
    "intent_fist": {
        "emoji": "👊", "name": "Fist Intent",
        "effects": "Bypasses Armor — Direct Dantian Qi Damage",
    },
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class AptitudeProfile:
    """Complete spiritual aptitude snapshot for one cultivator.

    Values for elemental aptitudes and intents are 0–100.
    yin_yang_balance is -100 (Pure Yin) to +100 (Pure Yang).
    special_root is None or a string tag ('chaos', future roots).
    """
    yin_yang_balance: int = 0

    affinity_fire:  int = 10
    affinity_water: int = 10
    affinity_wood:  int = 10
    affinity_metal: int = 10
    affinity_earth: int = 10
    affinity_qi:    int = 10

    intent_sword: int = 5
    intent_sabre: int = 5
    intent_spear: int = 5
    intent_fist:  int = 5

    special_root: str | None = field(default=None)

    def to_db_dict(self) -> dict:
        """Return only the columns that land in the `cultivators` table."""
        d = asdict(self)
        return d  # every field maps 1:1 to a DB column

    def dominant_element(self) -> str:
        """Return the key of the highest elemental aptitude."""
        return max(ELEMENT_KEYS, key=lambda k: getattr(self, k))

    def dominant_intent(self) -> str:
        """Return the key of the highest martial intent."""
        return max(INTENT_KEYS, key=lambda k: getattr(self, k))


# ---------------------------------------------------------------------------
# Awakening roll
# ---------------------------------------------------------------------------

def _distribute_pool(count: int, pool: int, max_single: int) -> list[int]:
    """Distribute `pool` points across `count` slots, each capped at `max_single`."""
    values = [0] * count
    remaining = pool
    # Safety: clamp in case pool > count * max_single
    remaining = min(remaining, count * max_single)
    indices = list(range(count))
    random.shuffle(indices)
    for i in indices:
        give = random.randint(0, min(remaining, max_single))
        values[i] = give
        remaining -= give
        if remaining <= 0:
            break
    # Distribute any leftovers (from floored random choices) greedily
    for i in indices:
        if remaining <= 0:
            break
        can_give = max_single - values[i]
        give = min(remaining, can_give)
        values[i] += give
        remaining -= give
    return values


def generate_initial_aptitudes() -> AptitudeProfile:
    """Roll a fresh Spiritual Aptitude Profile for a newly registered cultivator.

    Algorithm:
      1. 1% chance → Chaos Five-Element Root: each element = randint(20, 25),
         intents distributed from standard 30-point pool.
      2. Otherwise: 60-point pool spread across 6 elements (max 25 each),
         30-point pool spread across 4 intents (max 15 each).
      3. yin_yang_balance starts at 0 for all.
    """
    profile = AptitudeProfile()

    if random.random() < CHAOS_ROOT_CHANCE:
        # Chaos Five-Element Root — balanced high values across all 6 elements
        profile.special_root = CHAOS_ROOT_TAG
        for key in ELEMENT_KEYS:
            setattr(profile, key, random.randint(20, 25))
    else:
        element_vals = _distribute_pool(ELEMENT_COUNT, ELEMENT_POOL, ELEMENT_MAX_SINGLE)
        for key, val in zip(ELEMENT_KEYS, element_vals):
            setattr(profile, key, val)

    intent_vals = _distribute_pool(INTENT_COUNT, INTENT_POOL, INTENT_MAX_SINGLE)
    for key, val in zip(INTENT_KEYS, intent_vals):
        setattr(profile, key, val)

    return profile


# ---------------------------------------------------------------------------
# Growth helpers
# ---------------------------------------------------------------------------

def clamp_aptitude(value: int, key: str) -> int:
    """Clamp an aptitude value to its legal range."""
    if key == "yin_yang_balance":
        return max(-100, min(100, value))
    return max(0, min(100, value))


def add_aptitude(profile: AptitudeProfile, key: str, amount: int) -> AptitudeProfile:
    """Return a new profile with `key` incremented by `amount` and clamped."""
    if not hasattr(profile, key):
        raise ValueError(f"Unknown aptitude key: {key!r}")
    new_val = clamp_aptitude(getattr(profile, key) + amount, key)
    return AptitudeProfile(**{**asdict(profile), key: new_val})


# ---------------------------------------------------------------------------
# Stat multiplier integration (consumed by core/math.py)
# ---------------------------------------------------------------------------

def aptitude_stat_multipliers(profile: AptitudeProfile | dict) -> dict[str, float]:
    """Return a flat dict of combat/cultivation multipliers derived from aptitudes.

    All multipliers are additive bonuses expressed as fractions (0.05 = +5%).
    core/math.py applies these on top of the base formulas.

    Scaling formula: (aptitude / 100) * max_bonus
    """
    if isinstance(profile, dict):
        get = profile.get
    else:
        get = lambda k, d=0: getattr(profile, k, d)  # noqa: E731

    def scale(key: str, max_bonus: float) -> float:
        return round((get(key, 0) / 100.0) * max_bonus, 4)

    # Yin-Yang: normalized to [-1, 1]
    yy = get("yin_yang_balance", 0) / 100.0

    return {
        # ── Fire (🔥) ──────────────────────────────────────────────────────
        "crit_chance_bonus":      scale("affinity_fire", 0.20),   # up to +20% crit chance
        "crit_multiplier_bonus":  scale("affinity_fire", 0.50),   # up to +50% crit multiplier

        # ── Water (💧) ────────────────────────────────────────────────────
        "evasion_bonus":          scale("affinity_water", 0.15),  # up to +15% evasion
        "speed_bonus":            scale("affinity_water", 0.10),  # up to +10% speed
        "vitality_recovery":      scale("affinity_water", 0.10),  # up to +10% HP regen

        # ── Wood (🪵) ─────────────────────────────────────────────────────
        "debuff_immunity_bonus":  scale("affinity_wood", 0.20),   # up to +20% debuff resist

        # ── Metal (🪙) ────────────────────────────────────────────────────
        "armor_penetration":      scale("affinity_metal", 0.25),  # up to +25% armor pen
        "raw_damage_bonus":       scale("affinity_metal", 0.15),  # up to +15% raw damage

        # ── Earth (🪨) ────────────────────────────────────────────────────
        "cc_resistance":          scale("affinity_earth", 0.20),  # up to +20% CC resist
        "barrier_shielding":      scale("affinity_earth", 0.15),  # up to +15% barrier

        # ── Qi (✨) ───────────────────────────────────────────────────────
        "qi_regen_bonus":         scale("affinity_qi", 0.30),     # up to +30% Qi regen
        "qi_gain_bonus":          scale("affinity_qi", 0.20),     # up to +20% Qi per action
        "dantian_efficiency":     scale("affinity_qi", 0.15),     # up to +15% capacity

        # ── Sword Intent (🗡️) ─────────────────────────────────────────────
        "multi_hit_chance":       scale("intent_sword", 0.15),    # up to +15% multi-hit

        # ── Sabre Intent (🪓) ─────────────────────────────────────────────
        "cleave_damage_bonus":    scale("intent_sabre", 0.20),
        "lifesteal_bonus":        scale("intent_sabre", 0.10),

        # ── Spear Intent (🔱) ─────────────────────────────────────────────
        "counter_attack_bonus":   scale("intent_spear", 0.15),
        "armor_break_chance":     scale("intent_spear", 0.12),

        # ── Fist Intent (👊) ──────────────────────────────────────────────
        "dantian_damage_bonus":   scale("intent_fist", 0.25),     # armor-ignoring damage

        # ── Yin-Yang Balance ──────────────────────────────────────────────
        # Yang (+): physical fortitude, external power, crit
        # Yin (−): phantom evasion, heart demon resistance
        "yang_fortitude":         max(0.0, round(yy * 0.10, 4)),
        "yin_hd_resistance":      max(0.0, round(-yy * 0.10, 4)),
    }


# ---------------------------------------------------------------------------
# Prerequisite check (used by core/items.py)
# ---------------------------------------------------------------------------

APTITUDE_PREREQ_KEYS = set(ELEMENT_KEYS) | set(INTENT_KEYS) | {"yin_yang_balance"}


def check_prerequisites(
    reqs: dict,
    profile: AptitudeProfile | dict,
) -> tuple[bool, list[str]]:
    """Verify a dict of aptitude requirements against a cultivator's profile.

    `reqs` example:
        {"min_affinity_fire": 40, "min_intent_sword": 30}

    Returns (ok: bool, missing: list[str]) where missing contains human-readable
    failure messages (e.g. "Fire Aptitude 35 / 40 required").
    """
    if isinstance(profile, dict):
        get = lambda k, d=0: profile.get(k, d)  # noqa: E731
    else:
        get = lambda k, d=0: getattr(profile, k, d)  # noqa: E731

    missing: list[str] = []
    for req_key, req_val in reqs.items():
        # req_key format: "min_affinity_fire" → aptitude key "affinity_fire"
        apt_key = req_key.removeprefix("min_")
        if apt_key not in APTITUDE_PREREQ_KEYS:
            continue
        current = get(apt_key, 0)
        if current < req_val:
            meta = ELEMENT_META.get(apt_key) or INTENT_META.get(apt_key)
            display = meta["name"] if meta else apt_key.replace("_", " ").title()
            missing.append(f"{display}: {current} / {req_val} required")

    return (len(missing) == 0), missing


# ---------------------------------------------------------------------------
# Yin-Yang colour helper (for embed colour-coding)
# ---------------------------------------------------------------------------

def yin_yang_color(balance: int) -> int:
    """Return a discord.py-compatible hex colour based on Yin-Yang balance."""
    if balance >= 60:
        return 0xFFD700   # Gold — Pure Yang / Solar
    if balance >= 20:
        return 0x00BFFF   # Deep Sky Blue — Yang lean
    if balance <= -60:
        return 0x8A2BE2   # Blueviolet — Pure Yin / Phantom
    if balance <= -20:
        return 0x9370DB   # Medium Purple — Yin lean
    return 0x00FFFF       # Cyan — balanced
