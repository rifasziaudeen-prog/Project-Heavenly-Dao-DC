"""Deterministic Dao Laws engine.

Pure Python logic for law access requirements, insight gains, rank
progression, resistance, and Dao Fusion gates — no Discord or DB
dependencies. All tuning numbers live here as named constants, so balance
edits are one-line changes in a single file.

v1.6.0: the fuzzy 0-100% milestone system (25/50/75/100) was replaced with
5 discrete Ranks unlocking at 20/40/60/80/100 mastery. Insight gain is now
deterministic and scales with the cultivator's 悟性 (comprehension stat).
Resistance is 5% per rank (rank 1 = 5% ... rank 5 = 25%).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ranks (5) — what players see instead of raw percentages
# ---------------------------------------------------------------------------
LAW_RANK_THRESHOLDS: Tuple[int, ...] = (20, 40, 60, 80, 100)

LAW_RANKS: Tuple[Tuple[str, str], ...] = (
    ("Insight", "洞察"),
    ("Comprehension", "领悟"),
    ("Realization", "真悟"),
    ("Enlightenment", "明悟"),
    ("Transcendence", "超脱"),
)

LAW_RESISTANCE_PER_RANK = 0.05    # rank 1 = 5% ... rank 5 = 25%

# ---------------------------------------------------------------------------
# Insight gain — aptitude (悟性) is learning speed
# ---------------------------------------------------------------------------
LAW_INSIGHT_BASE = 2              # mastery points per /comprehend at 悟性 0-99
INSIGHT_SOURCE_FLAT: Dict[str, int] = {
    "comprehend": 0,
    "secret_realm": 4,
    "tribulation": 8,
    "world_boss": 1,
    "ancient_text": 2,
    "sect_meditation": 1,
}


def can_comprehend_law(cultivator: Dict[str, Any], law: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if cultivator meets requirements to study a Dao Law (Realm & Comprehension)."""
    req_realm = law.get("realm_required", 5)
    req_comp = law.get("comprehension_required", 200)

    if cultivator.get("realm_tier", 1) < req_realm:
        return False, f"Requires realm tier {req_realm} (Nascent Soul/higher) to comprehend this fundamental law."

    if cultivator.get("comprehension", 10) < req_comp:
        return False, f"Requires {req_comp} Comprehension to grasp the threads of this law. You have {cultivator.get('comprehension', 10)}."

    return True, None


# ---------------------------------------------------------------------------
# Ranks & resistance
# ---------------------------------------------------------------------------
def law_rank(mastery: float) -> int:
    """Rank 0-5: how many rank thresholds have been met (0 = unranked below 20%)."""
    rank = 0
    for threshold in LAW_RANK_THRESHOLDS:
        if mastery >= threshold:
            rank += 1
    return rank


def law_rank_label(mastery: float) -> str:
    """Human-readable rank label, e.g. 'Rank 3 · Realization (真悟)'."""
    rank = law_rank(mastery)
    if rank == 0:
        return "Unranked 未悟"
    en, cn = LAW_RANKS[rank - 1]
    return f"Rank {rank} · {en} ({cn})"


def next_rank_progress(mastery: float) -> Tuple[int, float]:
    """Points needed to reach the next rank: (points_needed, mastery_at_next_rank).

    Returns (0, 100.0) at max rank.
    """
    rank = law_rank(mastery)
    if rank >= len(LAW_RANK_THRESHOLDS):
        return 0, 100.0
    next_at = LAW_RANK_THRESHOLDS[rank]
    return max(0, next_at - int(mastery)), next_at


def law_resistance(mastery: float) -> float:
    """Damage reduction against attacks of this law's type (5% per rank)."""
    return round(law_rank(mastery) * LAW_RESISTANCE_PER_RANK, 4)


def law_counter_advantage(my_mastery: float, their_mastery: float) -> bool:
    """2+ ranks ahead -> deterministic counter (full nullification, no RNG)."""
    return law_rank(my_mastery) - law_rank(their_mastery) >= 2


# ---------------------------------------------------------------------------
# Insight gain — deterministic, aptitude (悟性) = learning speed
# ---------------------------------------------------------------------------
def calculate_insight_gain(comprehension: int, source: str = "comprehend") -> float:
    """Mastery points from one enlightenment action.

    Deterministic: 2 base + 悟性//100, plus a flat per-source bonus
    (secret realms +4, tribulations +8, ...). No randomness, no percentages.
    """
    flat = INSIGHT_SOURCE_FLAT.get(source, 0)
    return float(LAW_INSIGHT_BASE + max(0, int(comprehension)) // 100 + flat)


def check_rank_ups(current_mastery: float, previous_mastery: float) -> List[int]:
    """Rank numbers crossed in this gain (1-5), e.g. [2] on entering Rank 2."""
    crossed: List[int] = []
    for i, threshold in enumerate(LAW_RANK_THRESHOLDS, start=1):
        if previous_mastery < threshold <= current_mastery:
            crossed.append(i)
    return crossed


# ---------------------------------------------------------------------------
# Effect aggregation — rank thresholds now key the effect JSON (20/40/60/80/100)
# ---------------------------------------------------------------------------
_AGG_FIELDS = ("damage_bonus", "dodge_bonus", "cooldown_reduction", "breakthrough_bonus")


def _parse_effects(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def resolve_law_effects(cultivator_laws: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate active stat bonuses and techniques across all player law masteries.

    Every threshold key present in a law's mastery_effect JSON applies once the
    cultivator's mastery reaches that key (20/40/60/80/100).
    """
    aggregated = {field: 0.0 for field in _AGG_FIELDS}
    techniques: List[str] = []

    for item in cultivator_laws:
        mastery = item.get("mastery_percentage", 0.0)
        effects = _parse_effects(item.get("mastery_effect", {}))

        for threshold_str, effect in effects.items():
            if not threshold_str.isdigit():
                continue
            if mastery < float(threshold_str):
                continue
            if not isinstance(effect, dict):
                continue
            for field in _AGG_FIELDS:
                aggregated[field] += float(effect.get(field, 0.0))
            if "technique" in effect:
                techniques.append(effect["technique"])

    return {
        "damage_bonus": aggregated["damage_bonus"],
        "breakthrough_bonus": aggregated["breakthrough_bonus"],
        "cooldown_reduction": aggregated["cooldown_reduction"],
        "dodge_bonus": aggregated["dodge_bonus"],
        "unlocked_techniques": techniques,
    }


def has_dao_fusion_requirement(cultivator_laws: List[Dict[str, Any]]) -> bool:
    """Check if cultivator has reached Rank 5 (100.0% mastery) in ANY law (required for Dao Fusion)."""
    return any(item.get("mastery_percentage", 0.0) >= 100.0 for item in cultivator_laws)
