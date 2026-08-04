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
"""
from __future__ import annotations

import math
import random

# ---------------------------------------------------------------------------
# Realm taxonomy (bilingual)
# ---------------------------------------------------------------------------
REALMS: dict[int, tuple[str, str]] = {
    1: ("Mortal", "凡人"),
    2: ("Qi Condensation", "炼气"),
    3: ("Foundation Establishment", "筑基"),
    4: ("Core Formation", "金丹"),
    5: ("Nascent Soul", "元婴"),
    6: ("Spirit Severing", "化神"),
    7: ("Dao Fusion", "合体"),
    8: ("Tribulation", "渡劫"),
    9: ("Immortal", "大乘"),
}
SUB_STAGES: dict[int, tuple[str, str]] = {
    1: ("Early", "初期"),
    2: ("Mid", "中期"),
    3: ("Late", "后期"),
    4: ("Peak", "巅峰"),
}
MAX_TIER = 9

# ---------------------------------------------------------------------------
# Qi economy (review: exponential base, controlled by diminishing returns)
# ---------------------------------------------------------------------------
BASE_QI: dict[int, int] = {
    1: 8, 2: 35, 3: 140, 4: 560, 5: 2_200,
    6: 9_000, 7: 36_000, 8: 150_000, 9: 600_000,
}
QI_CAPACITY: dict[int, int] = {
    1: 1_000, 2: 2_500, 3: 6_000, 4: 15_000, 5: 40_000,
    6: 100_000, 7: 300_000, 8: 1_000_000, 9: 5_000_000,
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
    2: 15.0, 3: 31.0, 4: 63.0, 5: 126.0,
    6: 251.0, 7: 500.0, 8: 1000.0, 9: 1886.0,
}
SUB_STAGE_DIFFICULTY_FACTOR = 0.25   # deepening mastery within a realm gets harder

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
    return SUB_STAGES.get(stage, ("?", "?"))[0]


def sub_stage_cn(stage: int) -> str:
    return SUB_STAGES.get(stage, ("?", "?"))[1]


def realm_label(tier: int, sub_stage: int, lang: str = "bilingual") -> str:
    """e.g. 'Foundation Establishment (Mid) · 筑基中期' or 'Foundation Establishment (Mid)'."""
    en, cn = REALMS.get(tier, ("Unknown", "???"))
    sen, scn = SUB_STAGES.get(sub_stage, ("?", "?"))
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
) -> int:
    """Total Qi for one action.

    * Comprehension: logarithmic (100 -> 2x, 500 -> ~2.7x; never 6x)
    * Array: linear but capped at +50%
    * Companions: additive, hard-capped at 2x
    * Source multiplier: message = 10% of a cultivate
    * Aptitude (v1.1.0): Qi aptitude adds qi_gain_bonus (up to +20%)
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
    return int(base * comp_bonus * array_bonus * companion_bonus * source_mult * apt_qi_bonus)


# ---------------------------------------------------------------------------
# Breakthrough
# ---------------------------------------------------------------------------
def difficulty_for_breakthrough(current_tier: int, current_sub_stage: int) -> float:
    """Peak -> next tier uses the entry difficulty; in-realm mastery scales up."""
    if current_sub_stage >= 4:
        return DIFFICULTY.get(
            current_tier + 1,
            15.0 * (1.95 ** max(0, current_tier - 1)),
        )
    base = DIFFICULTY.get(current_tier, 15.0)
    return base * (1.0 + (current_sub_stage - 1) * SUB_STAGE_DIFFICULTY_FACTOR)


def calculate_breakthrough_probability(
    stats: dict[str, float | int],
    current_tier: int,
    current_sub_stage: int,
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
    difficulty = difficulty_for_breakthrough(current_tier, current_sub_stage)
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


def next_realm_step(tier: int, sub_stage: int) -> tuple[int, int, bool]:
    """Returns (new_tier, new_sub_stage, is_tier_up).

    Advancement caps at the summit (Immortal Peak, 9/4) — a successful
    tribulation there never regresses sub-stages.
    """
    if tier >= MAX_TIER and sub_stage >= 4:
        return MAX_TIER, 4, False
    if tier >= MAX_TIER:
        return MAX_TIER, sub_stage + 1, False
    if sub_stage >= 4:
        return tier + 1, 1, True
    return tier, sub_stage + 1, False


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
