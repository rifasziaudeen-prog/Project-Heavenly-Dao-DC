"""Dao Bond engine — player-to-player social mechanics (review v2).

Companions are REAL PEOPLE now. `dao_bonds` models relationships between
cultivators; all rules here are deterministic and auditable (no LLM, no RNG
for validation). The gender matrix enforces the admin's decree: nobody marries
their own gender.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

# --- Bond types -------------------------------------------------------------
DAO_COMPANION = "dao_companion"
SWORN_SIBLING = "sworn_sibling"
MASTER_DISCIPLE = "master_disciple"
RIVAL = "rival"
SECT_SIBLING = "sect_sibling"
DUAL_CULTIVATION = "dual_cultivation_partner"

BOND_TYPES = (
    DAO_COMPANION, SWORN_SIBLING, MASTER_DISCIPLE,
    RIVAL, SECT_SIBLING, DUAL_CULTIVATION,
)
ROMANTIC_BONDS = (DAO_COMPANION, DUAL_CULTIVATION)

BOND_TYPE_LABELS = {
    DAO_COMPANION: "道侣 Dao Companion",
    SWORN_SIBLING: "义兄姊 Sworn Sibling",
    MASTER_DISCIPLE: "师徒 Master-Disciple",
    RIVAL: "宿敌 Rival",
    SECT_SIBLING: "同门 Sect Sibling",
    DUAL_CULTIVATION: "双修伴侣 Dual Cultivation Partner",
}

# --- Rule constants ---------------------------------------------------------
MIN_REALM_TIER = 2          # Qi Condensation — Mortals cannot form Dao Bonds
ROMANTIC_REALM_GAP = 1     # romantic bonds: within 1 realm
STANDARD_REALM_GAP = 3     # other bonds: up to 3 realms apart
MASTER_TIER_DIFFERENCE = 2  # a master must be 2+ realms higher

# Polygamy limits (active bonds per player, per type)
BOND_LIMITS = {
    DAO_COMPANION: 3,
    SWORN_SIBLING: 5,
    MASTER_DISCIPLE: 3,   # disciples under one master
    RIVAL: 1,
    SECT_SIBLING: 10,
    DUAL_CULTIVATION: 1,
}
DISCIPLE_MASTER_LIMIT = 1  # one master per disciple

# Dual cultivation
DUAL_COOLDOWN_HOURS = 4
DUAL_MIN_BOND_TIER = 3
DUAL_QI_BONUS_CAP = 2.0
DUAL_HEART_DEMON_REDUCTION = 0.03
DUAL_BOND_POINTS = 50
BOND_TIER_POINT_THRESHOLD = 250   # cumulative points needed per tier (tier*250)

# Severance drama
SEVER_HEART_DEMON_PER_TIER = 0.05
SEVER_BETRAYER_KARMA = -100
RAGE_BUFF_DAYS = 7
RAGE_BREAKTHROUGH_BONUS = 0.15
RAGE_TITLE = "Betrayed"

# Fickle rebond — the Heaven frowns on those who sever a bond and immediately
# chase new love. For now this is pure stigma (a title + public scandal); it is
# also the intended seed for the demonic-cultivation path (Phase 3).
FICKLE_REBOND_WINDOW_DAYS = 7
FICKLE_TITLE = "Fickle Heart"

# --- Gender helpers ---------------------------------------------------------
def parse_gender_map(raw: str | None) -> dict[str, str]:
    """Parse the per-guild role->gender JSON. Invalid entries are dropped."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if v in ("male", "female")}


def gender_of(role_map: dict[str, str], member_roles) -> str | None:
    """First gender found across the member's roles (role ids as strings)."""
    for role in member_roles:
        gender = role_map.get(str(role.id))
        if gender in ("male", "female"):
            return gender
    return None

# --- Validation -------------------------------------------------------------
def is_romantic(bond_type: str) -> bool:
    return bond_type in ROMANTIC_BONDS


def gender_pair_allowed(gender_a: str, gender_b: str, bond_type: str) -> bool:
    """Same-gender pairs cannot form romantic bonds (marriage lock)."""
    if is_romantic(bond_type) and gender_a == gender_b:
        return False
    return True


def realm_gap_allowed(tier_a: int, tier_b: int, bond_type: str) -> bool:
    max_gap = ROMANTIC_REALM_GAP if is_romantic(bond_type) else STANDARD_REALM_GAP
    return abs(tier_a - tier_b) <= max_gap


def bond_limit_for(bond_type: str, self_tier: int, other_tier: int) -> int:
    """Active-bond limit for the requesting player.

    Master-Disciple is directional: the higher realm holds the master slot
    (up to BOND_LIMITS disciples); the lower realm is the disciple (one master).
    """
    if bond_type == MASTER_DISCIPLE:
        return (
            BOND_LIMITS[MASTER_DISCIPLE]
            if self_tier > other_tier
            else DISCIPLE_MASTER_LIMIT
        )
    return BOND_LIMITS.get(bond_type, 1)


def validate_bond_formation(
    *,
    self_gender: str | None,
    other_gender: str | None,
    bond_type: str,
    self_tier: int,
    other_tier: int,
    active_count: int,
    existing_pair: bool,
) -> tuple[bool, str]:
    """Returns (ok, reason). Deterministic, auditable — drop into the command."""
    if bond_type not in BOND_TYPES:
        return False, f"Unknown bond type '{bond_type}'."
    if not self_gender or not other_gender:
        return False, (
            "Both players must claim a gender role (set by the Heaven via "
            "`/dao_config`) before forming Dao Bonds."
        )
    if not gender_pair_allowed(self_gender, other_gender, bond_type):
        return False, (
            f"Same-gender pairs cannot form **{BOND_TYPE_LABELS.get(bond_type, bond_type)}**"
            " bonds — the Heaven forbids marrying one's own kind."
        )
    if self_tier < MIN_REALM_TIER or other_tier < MIN_REALM_TIER:
        weak = "you have" if self_tier < MIN_REALM_TIER else "they have"
        return False, (
            "Only those who have reached **Qi Condensation (炼气)** may form Dao Bonds — "
            f"right now {weak} not yet stepped beyond the mortal veil. Cultivate and "
            "`/breakthrough` first."
        )
    if not realm_gap_allowed(self_tier, other_tier, bond_type):
        max_gap = ROMANTIC_REALM_GAP if is_romantic(bond_type) else STANDARD_REALM_GAP
        return False, (
            f"Realm gap of {abs(self_tier - other_tier)} exceeds the allowed "
            f"{max_gap} for this bond type."
        )
    if bond_type == MASTER_DISCIPLE and abs(self_tier - other_tier) < MASTER_TIER_DIFFERENCE:
        return False, "A master must be at least 2 realms higher than the disciple."
    if existing_pair:
        return False, "A Dao Bond already exists between you two."
    limit = bond_limit_for(bond_type, self_tier, other_tier)
    if active_count >= limit:
        return False, (
            f"You already hold the maximum of **{limit}** active "
            f"{BOND_TYPE_LABELS.get(bond_type, bond_type)} bond(s)."
        )
    return True, "valid"


# --- Synergy (real stats, no RNG) -------------------------------------------
def calculate_bond_synergy(
    stats_a: dict,
    stats_b: dict,
    karma_a: int,
    karma_b: int,
    tier_a: int,
    tier_b: int,
    bond_tier: int,
) -> float:
    """Complementary stats + shared karma path + realm proximity + bond maturity.

    From the review: closer/complementary stats = higher synergy; same karma
    sign = 1.2x, opposed = 0.7x; realm gap penalizes; bond tier compounds.
    """
    stat_pairs = [
        (stats_a.get("strength", 10), stats_b.get("spirit", 10)),   # complementary
        (stats_a.get("spirit", 10), stats_b.get("strength", 10)),   # complementary
        (stats_a.get("comprehension", 10), stats_b.get("comprehension", 10)),  # shared
    ]
    stat_synergy = sum(
        (a + b) / max(abs(a - b), 1) for a, b in stat_pairs
    ) / 100
    same_path = (karma_a >= 0 and karma_b >= 0) or (karma_a < 0 and karma_b < 0)
    karma_synergy = 1.2 if same_path else 0.7
    realm_penalty = max(0.5, 1.0 - (abs(tier_a - tier_b) * 0.15))
    tier_mult = 1.0 + max(1, bond_tier) * 0.03
    return stat_synergy * karma_synergy * realm_penalty * tier_mult


# --- Bond progression -------------------------------------------------------
def bond_tier_from_points(points: int) -> int:
    """Cumulative points -> tier: tier T costs T*250 points (cap 20)."""
    tier = 1
    required = 0
    for t in range(1, 20):
        required += t * BOND_TIER_POINT_THRESHOLD
        if points >= required:
            tier = t + 1
        else:
            break
    return tier


# --- Severance drama --------------------------------------------------------
def severance_effects(bond_tier: int) -> dict:
    """Both take Heart Demon; the severer loses karma; the victim rages."""
    return {
        "heart_demon_both": min(1.0, bond_tier * SEVER_HEART_DEMON_PER_TIER),
        "betrayer_karma": SEVER_BETRAYER_KARMA,
        "rage_title": RAGE_TITLE,
        "rage_bonus": RAGE_BREAKTHROUGH_BONUS,
        "rage_duration_days": RAGE_BUFF_DAYS,
    }


def rage_until_str(days: int = RAGE_BUFF_DAYS) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def is_raging(rage_until: str | None) -> bool:
    if not rage_until:
        return False
    try:
        expiry = datetime.strptime(rage_until, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return False
    return expiry > datetime.now(timezone.utc)


# --- Fickle rebond detection -----------------------------------------------
def is_fickle_rebond(
    new_bond_type: str,
    last_severed_at: str | None,
    severed_by_self: bool,
    *,
    now: datetime | None = None,
) -> bool:
    """Did the player sever a bond and immediately pursue new *romance*?

    Triggers only for romantic bonds (Dao Companion / Dual Cultivation Partner)
    within `FICKLE_REBOND_WINDOW_DAYS` of a severance that THIS player initiated.
    Victims (the one who was left) are exempt — they already got the rage buff.
    Pure function: pass the last severance row for the player and let the cog
    decide what stigma to apply.
    """
    if not is_romantic(new_bond_type):
        return False
    if not severed_by_self or not last_severed_at:
        return False
    now = now or datetime.now(timezone.utc)
    try:
        severed_at = datetime.strptime(last_severed_at, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return False
    return (now - severed_at).days < FICKLE_REBOND_WINDOW_DAYS
