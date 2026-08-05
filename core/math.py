"""Deterministic game math for the Heavenly Dao Engine.

Every formula here is 100% hardcoded and auditable — no LLM involvement.
Balancing follows the Kimi review (v1.0): diminishing returns on Qi,
exponential breakthrough difficulty, non-linear Heart Demon penalty,
Dao Mercy pity system, and Heavenly Dao Erasure with charm counterplay.

v1.1.0 additions:
  * calculate_qi_gain accepts `aptitude_multipliers` from core.affinities
    (qi_gain_bonus and qi_regen_bonus applied on top of existing formula).
  * calculate_breakthrough_probability accepts `aptitude_multipliers` for
    future aptitude-gated breakthrough bonuses (currently no-op).

v1.4.0 additions (Part 1 of the combat & realm expansion plan):
  * 16 realms × 9 layers (was 9 tiers × 4 sub-stages). Realm names follow the
    "Next Steps" blueprint: Void Refinement (炼虚) inserted, tiers 7-9 shifted.
  * Transcendence prestige loop at Beyond Dao (16th realm, 9th layer):
    voluntary reset that grants permanent flat gifts + stacking passives.
  * calculate_qi_gain accepts a flat_bonus for transcendence-granted Qi.
"""
from __future__ import annotations

import json
import math
import random

# ---------------------------------------------------------------------------
# Realm taxonomy (bilingual) — 16 realms
# ---------------------------------------------------------------------------
REALMS: dict[int, tuple[str, str]] = {
    1: ("Mortal", "凡人"),
    2: ("Qi Condensation", "炼气"),
    3: ("Foundation Establishment", "筑基"),
    4: ("Core Formation", "金丹"),
    5: ("Nascent Soul", "元婴"),
    6: ("Soul Transformation", "化神"),
    7: ("Void Refinement", "炼虚"),
    8: ("Dao Fusion", "合体"),
    9: ("Tribulation Transcendence", "渡劫"),
    10: ("True Immortal", "真仙"),
    11: ("Golden Immortal", "金仙"),
    12: ("Primordial Chaos", "混沌"),
    13: ("Dao Ancestor", "道祖"),
    14: ("Heavenly Venerable", "天尊"),
    15: ("Great Emperor", "大帝"),
    16: ("Beyond Dao", "超脱"),
}

# 9 layers within every realm. `SUB_STAGES` is kept as a legacy alias.
LAYERS: dict[int, tuple[str, str]] = {
    1: ("1st Layer", "一层"),
    2: ("2nd Layer", "二层"),
    3: ("3rd Layer", "三层"),
    4: ("4th Layer", "四层"),
    5: ("5th Layer", "五层"),
    6: ("6th Layer", "六层"),
    7: ("7th Layer", "七层"),
    8: ("8th Layer", "八层"),
    9: ("9th Layer", "九层"),
}
SUB_STAGES = LAYERS  # legacy alias for any external readers

MAX_TIER = 16
MAX_LAYER = 9

# ---------------------------------------------------------------------------
# Qi economy (review: exponential base, controlled by diminishing returns)
# ---------------------------------------------------------------------------
BASE_QI: dict[int, int] = {
    1: 8, 2: 35, 3: 140, 4: 560, 5: 2_200,
    6: 9_000, 7: 36_000, 8: 150_000, 9: 600_000,
    10: 2_400_000, 11: 9_600_000, 12: 38_400_000, 13: 153_600_000,
    14: 614_400_000, 15: 2_457_600_000, 16: 9_830_400_000,
}
QI_CAPACITY: dict[int, int] = {
    1: 1_000, 2: 2_500, 3: 6_000, 4: 15_000, 5: 40_000,
    6: 100_000, 7: 300_000, 8: 1_000_000, 9: 5_000_000,
    10: 20_000_000, 11: 80_000_000, 12: 300_000_000, 13: 1_200_000_000,
    14: 5_000_000_000, 15: 20_000_000_000, 16: 80_000_000_000,
}
# Passive chat Qi = 10% of a /cultivate (user requirement)
SOURCE_MULT: dict[str, float] = {
    "message": 0.10,
    "cultivate": 1.0,
    "sect_array": 0.30,
    "dual_cultivation": 2.5,
}

COMPANION_BONUS_CAP = 2.0     # hard cap: companions can never exceed 2x
ARRAY_BONUS_CAP = 0.50        # max +50% from sect array
MERCY_PER_FAILURE = 0.05      # Dao Mercy: +5% per failed attempt
MERCY_CAP = 0.25              # ... capped at +25%

# ---------------------------------------------------------------------------
# Breakthrough difficulty (review calibration table, entering tier N)
# ---------------------------------------------------------------------------
DIFFICULTY: dict[int, float] = {
    2: 15.0, 3: 31.0, 4: 63.0, 5: 126.0, 6: 251.0, 7: 500.0, 8: 1000.0,
    9: 1886.0, 10: 3600.0, 11: 6800.0, 12: 12900.0, 13: 24500.0,
    14: 46500.0, 15: 88000.0, 16: 167000.0,
}
# With 9 layers, 0.125 means the 9th layer (peak) is ~2x the realm's entry
# difficulty: (9 - 1) * 0.125 = 1.0.
SUB_STAGE_DIFFICULTY_FACTOR = 0.125

# Heavenly Dao Erasure
ERASURE_CHANCE = 0.005        # 0.5% — only on failure at tier 8+
ERASURE_MIN_TIER = 8
CHARM_DROP_CHANCE = 0.05      # 5% per successful breakthrough to find a charm

CHARM_TYPES = ("karmic_shield", "reincarnation_seed", "dao_heart_anchor")
CHARM_LABELS = {
    "karmic_shield": "护体符 (Karmic Shield)",
    "reincarnation_seed": "轮回种 (Reincarnation Seed)",
    "dao_heart_anchor": "道心锚 (Dao Heart Anchor)",
}

# ---------------------------------------------------------------------------
# Realm helpers
# ---------------------------------------------------------------------------
def realm_name(tier: int) -> str:
    return REALMS.get(tier, ("Unknown", "???"))[0]


def realm_cn(tier: int) -> str:
    return REALMS.get(tier, ("Unknown", "???"))[1]


def sub_stage_name(stage: int) -> str:
    return LAYERS.get(stage, ("?", "?"))[0]


def sub_stage_cn(stage: int) -> str:
    return LAYERS.get(stage, ("?", "?"))[1]


def realm_label(tier: int, sub_stage: int, lang: str = "bilingual") -> str:
    """e.g. 'Foundation Establishment (2nd Layer) · 筑基二层' or '... (2nd Layer)'."""
    en, cn = REALMS.get(tier, ("Unknown", "???"))
    sen, scn = LAYERS.get(sub_stage, ("?", "?"))
    if lang == "english":
        return f"{en} ({sen})"
    return f"{en} ({sen}) · {cn}{scn}"


def qi_capacity_for(tier: int) -> int:
    return QI_CAPACITY.get(tier, QI_CAPACITY[MAX_TIER])

# ---------------------------------------------------------------------------
# Qi gain — diminishing returns everywhere
# ---------------------------------------------------------------------------
def calculate_qi_gain(
    realm_tier: int,
    comprehension: int,
    source: str = "cultivate",
    sect_array_level: int = 0,
    has_sect: bool = False,
    active_companions: list[dict] | None = None,
    aptitude_multipliers: dict | None = None,
    flat_bonus: int = 0,
) -> int:
    """Total Qi for one action.

    * Comprehension: logarithmic (100 -> 2x, 500 -> ~2.7x; never 6x)
    * Array: linear but capped at +50%
    * Companions: additive, hard-capped at 2x
    * Source multiplier: message = 10% of a cultivate
    * Aptitude (v1.1.0): Qi aptitude adds qi_gain_bonus (up to +20%)
    * flat_bonus (v1.4.0): transcendence-granted flat Qi added last
    """
    base = BASE_QI.get(realm_tier, 10)
    comp_bonus = 1.0 + math.log10(1.0 + max(0, comprehension) / 10.0)
    array_bonus = (
        1.0 + min(max(0, sect_array_level) * 0.08, ARRAY_BONUS_CAP)
        if has_sect else 1.0
    )
    companion_bonus = 1.0
    for comp in active_companions or []:
        level = max(1, int(comp.get("intimacy_level", 1)))
        eff = min(level, 5) + math.log10(max(1.0, level - 4))
        companion_bonus += 0.05 + eff * 0.02
    companion_bonus = min(companion_bonus, COMPANION_BONUS_CAP)
    source_mult = SOURCE_MULT.get(source, 1.0)
    apt = aptitude_multipliers or {}
    apt_qi_bonus = 1.0 + apt.get("qi_gain_bonus", 0.0)
    return int(base * comp_bonus * array_bonus * companion_bonus * source_mult * apt_qi_bonus) + max(0, int(flat_bonus))


# ---------------------------------------------------------------------------
# Breakthrough
# ---------------------------------------------------------------------------
def difficulty_for_breakthrough(current_tier: int, current_layer: int) -> float:
    """9th layer -> next realm uses the entry difficulty; in-realm layers scale up."""
    if current_layer >= MAX_LAYER:
        return DIFFICULTY.get(
            current_tier + 1,
            15.0 * (1.95 ** max(0, current_tier - 1)),
        )
    base = DIFFICULTY.get(current_tier, 15.0)
    ramp = base * (1.0 + (current_layer - 1) * SUB_STAGE_DIFFICULTY_FACTOR)
    # Never make an in-realm layer harder than the tribulation that leaves the
    # realm (the 9th layer is the peak gate). Only realm 1's fallback base can
    # exceed its entry difficulty, but this guard keeps the curve monotone.
    entry = DIFFICULTY.get(current_tier + 1)
    return min(ramp, entry) if entry is not None else ramp


def calculate_breakthrough_probability(
    stats: dict[str, float | int],
    current_tier: int,
    current_layer: int,
    heart_demon_ratio: float = 0.0,
    karma_points: int = 0,
    has_sect: bool = False,
    sect_array_level: int = 0,
    failure_streak: int = 0,
    rage_bonus: float = 0.0,
    aptitude_multipliers: dict | None = None,
) -> float:
    """Deterministic success probability, clamped to [5%, 95%].

    P = (weighted stats / difficulty) * HD penalty * karma ± * sect
        + Dao Mercy (failure streak) + rage bonus (betrayed rage cultivation)

    v1.1.0: aptitude_multipliers accepted for future expansion (e.g. Wood
    aptitude reducing Heart Demon ratio penalty). Currently no-op.
    """
    stat_score = (
        stats.get("physique", 10) * 0.35
        + stats.get("spirit", 10) * 0.35
        + stats.get("luck", 5) * 0.20
        + stats.get("comprehension", 10) * 0.10
    )
    difficulty = difficulty_for_breakthrough(current_tier, current_layer)
    hd = max(0.0, min(1.0, heart_demon_ratio))
    hd_penalty = 1.0 - hd ** 1.5
    karma_bonus = 1.0 + max(-0.10, min(0.10, (karma_points or 0) / 1000.0))
    sect_bonus = 1.0 + (sect_array_level * 0.03) if has_sect else 1.0
    mercy = min(max(0, failure_streak) * MERCY_PER_FAILURE, MERCY_CAP)
    raw = (
        (stat_score / difficulty) * hd_penalty * karma_bonus * sect_bonus
        + mercy + max(0.0, rage_bonus)
    )
    return max(0.05, min(0.95, raw))


def next_realm_step(tier: int, layer: int) -> tuple[int, int, bool]:
    """Returns (new_tier, new_layer, is_tier_up).

    Advancement caps at the summit (Beyond Dao, 16/9) — a successful
    tribulation there never regresses layers.
    """
    if tier >= MAX_TIER and layer >= MAX_LAYER:
        return MAX_TIER, MAX_LAYER, False
    if tier >= MAX_TIER:
        return MAX_TIER, layer + 1, False
    if layer >= MAX_LAYER:
        return tier + 1, 1, True
    return tier, layer + 1, False


def erasure_should_roll(failed_attempt_tier: int, erasure_enabled: bool) -> bool:
    return erasure_enabled and failed_attempt_tier >= ERASURE_MIN_TIER


def roll_erasure() -> bool:
    return random.random() < ERASURE_CHANCE


# ---------------------------------------------------------------------------
# Heavenly Dao Erasure resolution (pure, unit-testable)
# ---------------------------------------------------------------------------
def resolve_erasure(charm_type: str | None) -> dict:
    """Decide what happens on a triggered erasure, given the active charm.

    Returns a dict with:
      erased        bool   — True if the cultivator falls back to Mortal
      keep_stats    str    — 'partial' (25% comp / 10% luck) | 'full' | 'none'
      qi_refund     float  — fraction of the POST-FAILURE (halved) Qi retained
                             after erasure (0.0 = reset to zero, 1.0 = keep the
                             halved remainder). The ordinary 50% failure
                             penalty always applies first, so charms only
                             soften the erasure's additional destruction.
      heart_demon_delta float — change applied to heart_demon_ratio
      title         str    — title granted
      charm_consumed bool
    """
    if charm_type == "karmic_shield":
        return {
            "erased": False, "keep_stats": "none", "qi_refund": 1.0,
            "heart_demon_delta": 0.0, "title": "Heavenly Dao Resisted",
            "charm_consumed": True,
        }
    if charm_type == "reincarnation_seed":
        return {
            "erased": True, "keep_stats": "full", "qi_refund": 0.0,
            "heart_demon_delta": 0.0, "title": "Past Life Reincarnator",
            "charm_consumed": True,
        }
    if charm_type == "dao_heart_anchor":
        return {
            "erased": False, "keep_stats": "none", "qi_refund": 1.0,
            "heart_demon_delta": -0.20, "title": "Dao Heart Anchored",
            "charm_consumed": True,
        }
    # No protection — the true Xianxia experience, but never account death
    return {
        "erased": True, "keep_stats": "partial", "qi_refund": 0.0,
        "heart_demon_delta": 0.0, "title": "Ashen Remnant",
        "charm_consumed": False,
    }


def apply_erasure_to_stats(stats: dict[str, int], keep: str) -> dict[str, int]:
    """Return adjusted stats after an erasure."""
    result = dict(stats)
    if keep == "partial":
        result["comprehension"] = max(10, int(result["comprehension"] * 0.25))
        result["luck"] = max(5, int(result["luck"] * 0.10))
    elif keep == "full":
        pass  # reincarnation seed: stats retained as past-life wisdom
    return result


# ---------------------------------------------------------------------------
# Transcendence — endgame prestige (Beyond Dao, 9th layer)
# ---------------------------------------------------------------------------
TRANSCENDENCE_REALM = MAX_TIER
TRANSCENDENCE_LAYER = MAX_LAYER
TRANSCENDENCE_BASE_CAPACITY = 1_000

# Every transcendence grants these permanent, stacking gifts (generous on
# purpose — this is the endgame reward loop).
TRANSCENDENCE_STAT_BONUS = 15           # +15 to all five core stats
TRANSCENDENCE_QI_CAPACITY_BONUS = 5_000  # +5,000 Qi capacity

# One cycling permanent passive per transcendence.
TRANSCENDENCE_PASSIVES: tuple[dict, ...] = (
    {"key": "boundless_dantian", "name": "Boundless Dantian 无垠丹田",
     "desc": "+100 flat Qi on every /cultivate", "qi_gain_bonus": 100},
    {"key": "immortal_vessel", "name": "Immortal Vessel 仙体天成",
     "desc": "+10,000 Qi capacity", "capacity_bonus": 10_000},
    {"key": "unyielding_dao_heart", "name": "Unyielding Dao Heart 道心不灭",
     "desc": "+10 Spirit (mental fortitude)", "spirit_bonus": 10},
    {"key": "celestial_fortune", "name": "Celestial Fortune 天命所归",
     "desc": "+5 Luck", "luck_bonus": 5},
    {"key": "ancient_soul", "name": "Ancient Soul 万古神魂",
     "desc": "+20 Comprehension", "comprehension_bonus": 20},
    {"key": "transcendent_physique", "name": "Transcendent Physique 超脱金身",
     "desc": "+20 Strength and +20 Physique", "strength_bonus": 20, "physique_bonus": 20},
)

_ROMAN_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def transcendence_title(count: int) -> str:
    """Title granted for the count-th transcendence (Transcendent I, II, ...)."""
    numeral = _ROMAN_NUMERALS[count - 1] if count <= len(_ROMAN_NUMERALS) else str(count)
    return f"Transcendent {numeral}"


def next_legacy_passive(count: int) -> dict:
    """The permanent passive granted on the count-th transcendence (cycles)."""
    return TRANSCENDENCE_PASSIVES[(count - 1) % len(TRANSCENDENCE_PASSIVES)]


def transcendence_payload(cultivator: dict) -> dict:
    """All permanent updates for a voluntary Transcendence (pure, testable).

    Resets active attributes (realm, layers, Qi, Heart Demon, failure streak)
    while permanently stacking:
      * +15 to strength / spirit / physique / comprehension / luck
      * +5,000 Qi capacity (survives future breakthroughs)
      * +100 flat Qi per /cultivate (from the cycling passive)
      * one cycling permanent passive + a Transcendent title

    The caller is responsible for appending the title to the titles JSON list.
    """
    next_count = int(cultivator.get("transcendence_count", 0)) + 1
    try:
        passives = json.loads(cultivator.get("legacy_passives") or "[]")
    except (json.JSONDecodeError, TypeError):
        passives = []
    if not isinstance(passives, list):
        passives = []
    passive = next_legacy_passive(next_count)
    passives.append(passive["key"])

    capacity_bonus = (
        int(cultivator.get("transcendence_capacity_bonus", 0))
        + TRANSCENDENCE_QI_CAPACITY_BONUS
        + int(passive.get("capacity_bonus", 0))
    )
    qi_gain_bonus = (
        int(cultivator.get("transcendence_qi_gain_bonus", 0))
        + int(passive.get("qi_gain_bonus", 0))
    )

    return {
        "realm_tier": 1,
        "realm_sub_stage": 1,
        "qi_current": 0,
        "qi_capacity": TRANSCENDENCE_BASE_CAPACITY + capacity_bonus,
        "transcendence_count": next_count,
        "transcendence_capacity_bonus": capacity_bonus,
        "transcendence_qi_gain_bonus": qi_gain_bonus,
        "legacy_passives": json.dumps(passives),
        "strength": int(cultivator.get("strength", 10)) + TRANSCENDENCE_STAT_BONUS + int(passive.get("strength_bonus", 0)),
        "spirit": int(cultivator.get("spirit", 10)) + TRANSCENDENCE_STAT_BONUS + int(passive.get("spirit_bonus", 0)),
        "physique": int(cultivator.get("physique", 10)) + TRANSCENDENCE_STAT_BONUS + int(passive.get("physique_bonus", 0)),
        "comprehension": int(cultivator.get("comprehension", 10)) + TRANSCENDENCE_STAT_BONUS + int(passive.get("comprehension_bonus", 0)),
        "luck": int(cultivator.get("luck", 5)) + TRANSCENDENCE_STAT_BONUS + int(passive.get("luck_bonus", 0)),
        "heart_demon_ratio": 0.0,
        "failure_streak": 0,
    }
