"""Tests for the player-to-player Dao Bond engine (core/dao_bonds.py)."""
from core import dao_bonds as bonds


def _validate(**overrides):
    kwargs = {
        "self_gender": "male", "other_gender": "female",
        "bond_type": bonds.DAO_COMPANION,
        "self_tier": 3, "other_tier": 3,
        "active_count": 0, "existing_pair": False,
    }
    kwargs.update(overrides)
    return bonds.validate_bond_formation(**kwargs)


def test_gender_matrix_romance_lock():
    # Same-gender romance is forbidden (the Heaven's decree)
    ok, _ = _validate(self_gender="male", other_gender="male",
                      bond_type=bonds.DAO_COMPANION)
    assert ok is False
    ok, _ = _validate(self_gender="female", other_gender="female",
                      bond_type=bonds.DUAL_CULTIVATION)
    assert ok is False
    # Same-gender non-romantic bonds are fine
    ok, _ = _validate(self_gender="male", other_gender="male",
                      bond_type=bonds.SWORN_SIBLING)
    assert ok is True
    # Opposite genders unlock everything
    ok, _ = _validate(self_gender="male", other_gender="female",
                      bond_type=bonds.DAO_COMPANION)
    assert ok is True
    ok, _ = _validate(self_gender="female", other_gender="male",
                      bond_type=bonds.DUAL_CULTIVATION)
    assert ok is True


def test_missing_gender_role_blocks_bonds():
    ok, reason = _validate(self_gender=None, other_gender="female")
    assert ok is False and "gender role" in reason
    ok, reason = _validate(self_gender="male", other_gender=None)
    assert ok is False


def test_mortals_cannot_form_bonds():
    # Only Qi Condensation (tier 2+) and above may form Dao Bonds.
    ok, reason = _validate(self_tier=1, other_tier=2,
                           bond_type=bonds.SWORN_SIBLING)
    assert ok is False and "Qi Condensation" in reason
    ok, reason = _validate(self_tier=2, other_tier=1,
                           bond_type=bonds.SWORN_SIBLING)
    assert ok is False and "Qi Condensation" in reason
    # Both at Qi Condensation is the minimum valid floor.
    ok, _ = _validate(self_tier=2, other_tier=2,
                      bond_type=bonds.SWORN_SIBLING,
                      self_gender="male", other_gender="male")
    assert ok is True


def test_realm_gap_rules():
    # Romantic bonds: within 1 realm
    ok, _ = _validate(self_tier=2, other_tier=3, bond_type=bonds.DAO_COMPANION)
    assert ok is True
    ok, _ = _validate(self_tier=2, other_tier=4, bond_type=bonds.DAO_COMPANION)
    assert ok is False
    # Standard bonds: up to 3 realms apart
    ok, _ = _validate(self_tier=2, other_tier=5, bond_type=bonds.SWORN_SIBLING,
                      self_gender="male", other_gender="male")
    assert ok is True
    ok, _ = _validate(self_tier=2, other_tier=6, bond_type=bonds.SWORN_SIBLING,
                      self_gender="male", other_gender="male")
    assert ok is False


def test_master_disciple_requires_gap():
    ok, _ = _validate(bond_type=bonds.MASTER_DISCIPLE, self_tier=3, other_tier=3)
    assert ok is False  # same realm cannot be master-disciple
    ok, _ = _validate(bond_type=bonds.MASTER_DISCIPLE, self_tier=5, other_tier=3)
    assert ok is True
    ok, _ = _validate(bond_type=bonds.MASTER_DISCIPLE, self_tier=3, other_tier=5)
    assert ok is True  # the lower realm may still be the disciple


def test_polygamy_limits():
    ok, _ = _validate(bond_type=bonds.DAO_COMPANION, active_count=2)
    assert ok is True
    ok, _ = _validate(bond_type=bonds.DAO_COMPANION, active_count=3)
    assert ok is False
    ok, _ = _validate(bond_type=bonds.RIVAL, active_count=1,
                      self_gender="male", other_gender="male")
    assert ok is False


def test_master_disciple_directional_limits():
    assert bonds.bond_limit_for(bonds.MASTER_DISCIPLE, 5, 3) == 3   # master slot
    assert bonds.bond_limit_for(bonds.MASTER_DISCIPLE, 3, 5) == 1   # disciple slot


def test_existing_pair_blocked():
    ok, _ = _validate(existing_pair=True)
    assert ok is False


def test_unknown_bond_type():
    ok, _ = _validate(bond_type="marriage")
    assert ok is False


def test_synergy_math():
    a = {"strength": 20, "spirit": 10, "comprehension": 15}
    b = {"strength": 10, "spirit": 20, "comprehension": 15}
    same_path = bonds.calculate_bond_synergy(a, b, 100, 50, 3, 3, 1)
    opposed = bonds.calculate_bond_synergy(a, b, 100, -50, 3, 3, 1)
    assert same_path > opposed  # karma alignment rewards the same path
    realm_gap = bonds.calculate_bond_synergy(a, b, 100, 50, 3, 8, 1)
    assert realm_gap < same_path  # realm proximity matters
    mature = bonds.calculate_bond_synergy(a, b, 100, 50, 3, 3, 10)
    assert mature > same_path  # bond tier compounds


def test_bond_tier_progression():
    assert bonds.bond_tier_from_points(0) == 1
    assert bonds.bond_tier_from_points(249) == 1
    assert bonds.bond_tier_from_points(250) == 2
    assert bonds.bond_tier_from_points(250 + 500) == 3
    assert bonds.bond_tier_from_points(10_000_000) == 20  # capped


def test_severance_effects_and_rage():
    fx = bonds.severance_effects(4)
    assert fx["heart_demon_both"] == 0.20
    assert fx["betrayer_karma"] == -100
    assert fx["rage_title"] == "Betrayed"
    assert fx["rage_bonus"] == 0.15
    assert fx["rage_duration_days"] == 7
    # Rage window helpers
    assert bonds.is_raging(bonds.rage_until_str(days=7)) is True
    assert bonds.is_raging(None) is False
    assert bonds.is_raging("2000-01-01 00:00:00") is False
    assert bonds.is_raging("not-a-date") is False


def test_fickle_rebond_romantic_only():
    """Rapid rebond stigma fires only for new romantic bonds."""
    from datetime import datetime, timedelta, timezone
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    # Romantic new bond within the window, severed by self -> fickle
    assert bonds.is_fickle_rebond(
        bonds.DAO_COMPANION, recent, severed_by_self=True) is True
    # Non-romantic new bond -> never fickle, even if recent and self-severed
    assert bonds.is_fickle_rebond(
        bonds.SWORN_SIBLING, recent, severed_by_self=True) is False
    assert bonds.is_fickle_rebond(
        bonds.RIVAL, recent, severed_by_self=True) is False


def test_fickle_rebond_victim_exempt():
    """The partner who was left (not the severer) is never flagged fickle."""
    from datetime import datetime, timedelta, timezone
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    assert bonds.is_fickle_rebond(
        bonds.DAO_COMPANION, recent, severed_by_self=False) is False


def test_fickle_rebond_window():
    """Older severances (>= 7 days) and missing data don't trigger."""
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    assert bonds.is_fickle_rebond(
        bonds.DAO_COMPANION, old, severed_by_self=True) is False
    assert bonds.is_fickle_rebond(
        bonds.DAO_COMPANION, None, severed_by_self=True) is False
    assert bonds.is_fickle_rebond(
        bonds.DAO_COMPANION, "not-a-date", severed_by_self=True) is False


def test_gender_map_parsing():
    assert bonds.parse_gender_map('{"111": "male", "222": "female"}') == {
        "111": "male", "222": "female",
    }
    assert bonds.parse_gender_map('{"111": "banana"}') == {}
    assert bonds.parse_gender_map(None) == {}
    assert bonds.parse_gender_map("not json") == {}
    assert bonds.parse_gender_map("[]") == {}
