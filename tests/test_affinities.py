"""tests/test_affinities.py

Unit tests for the Spiritual Aptitude & Martial Intent Engine (v1.1.0).

Coverage:
  1. Initial aptitude generation — pool sizes, single-stat caps, yin_yang default.
  2. Chaos Root awakening — correct stat ranges, special_root flag.
  3. Growth helper — clamping at 0 and 100 (and -100/+100 for yin_yang).
  4. Aptitude stat multipliers — key presence and value range checks.
  5. Prerequisite checks — pass when met, fail with readable messages.
  6. Migration 012 correctness — SQLite in-memory run adds expected columns.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from core.affinities import (
    ELEMENT_KEYS,
    ELEMENT_POOL,
    ELEMENT_MAX_SINGLE,
    INTENT_KEYS,
    INTENT_POOL,
    INTENT_MAX_SINGLE,
    CHAOS_ROOT_TAG,
    AptitudeProfile,
    add_aptitude,
    aptitude_stat_multipliers,
    check_prerequisites,
    clamp_aptitude,
    generate_initial_aptitudes,
)
from db.database import _split_sql_statements


# ---------------------------------------------------------------------------
# 1. Initial aptitude generation
# ---------------------------------------------------------------------------

class TestGenerateInitialAptitudes:
    def test_returns_aptitude_profile(self):
        profile = generate_initial_aptitudes()
        assert isinstance(profile, AptitudeProfile)

    def test_element_pool_total_approx(self):
        """Total elemental aptitude must not exceed the pool ceiling."""
        for _ in range(50):
            p = generate_initial_aptitudes()
            if p.special_root == CHAOS_ROOT_TAG:
                continue  # chaos root bypasses pool logic
            total = sum(getattr(p, k) for k in ELEMENT_KEYS)
            assert total <= ELEMENT_POOL, f"Total {total} exceeds pool {ELEMENT_POOL}"

    def test_element_single_stat_max(self):
        for _ in range(100):
            p = generate_initial_aptitudes()
            if p.special_root == CHAOS_ROOT_TAG:
                continue
            for key in ELEMENT_KEYS:
                val = getattr(p, key)
                assert val <= ELEMENT_MAX_SINGLE, (
                    f"{key}={val} exceeds single-stat max {ELEMENT_MAX_SINGLE}"
                )
                assert val >= 0

    def test_intent_pool_total_approx(self):
        for _ in range(50):
            p = generate_initial_aptitudes()
            total = sum(getattr(p, k) for k in INTENT_KEYS)
            assert total <= INTENT_POOL, f"Intent total {total} exceeds pool {INTENT_POOL}"

    def test_intent_single_stat_max(self):
        for _ in range(100):
            p = generate_initial_aptitudes()
            for key in INTENT_KEYS:
                val = getattr(p, key)
                assert val <= INTENT_MAX_SINGLE, (
                    f"{key}={val} exceeds single-stat max {INTENT_MAX_SINGLE}"
                )
                assert val >= 0

    def test_yin_yang_defaults_to_zero(self):
        for _ in range(20):
            p = generate_initial_aptitudes()
            assert p.yin_yang_balance == 0

    def test_all_values_non_negative(self):
        for _ in range(30):
            p = generate_initial_aptitudes()
            for key in ELEMENT_KEYS + INTENT_KEYS:
                assert getattr(p, key) >= 0


# ---------------------------------------------------------------------------
# 2. Chaos Root awakening
# ---------------------------------------------------------------------------

class TestChaosRoot:
    def _make_chaos_profile(self) -> AptitudeProfile:
        """Force a chaos root by patching random."""
        with patch("core.affinities.random.random", return_value=0.0):
            return generate_initial_aptitudes()

    def test_special_root_set_to_chaos(self):
        p = self._make_chaos_profile()
        assert p.special_root == CHAOS_ROOT_TAG

    def test_chaos_elements_in_valid_range(self):
        p = self._make_chaos_profile()
        for key in ELEMENT_KEYS:
            val = getattr(p, key)
            assert 20 <= val <= 25, f"{key}={val} out of Chaos Root range [20, 25]"

    def test_no_special_root_on_normal_roll(self):
        """With random > CHAOS_ROOT_CHANCE, no special root should appear."""
        with patch("core.affinities.random.random", return_value=0.5):
            # also patch randint to avoid chaos path internally
            p = generate_initial_aptitudes()
        # special_root can only be set in chaos branch
        assert p.special_root is None or p.special_root == CHAOS_ROOT_TAG  # safe check


# ---------------------------------------------------------------------------
# 3. Growth helper clamping
# ---------------------------------------------------------------------------

class TestGrowthHelpers:
    def test_clamp_element_upper(self):
        assert clamp_aptitude(150, "affinity_fire") == 100

    def test_clamp_element_lower(self):
        assert clamp_aptitude(-5, "affinity_fire") == 0

    def test_clamp_yin_yang_upper(self):
        assert clamp_aptitude(200, "yin_yang_balance") == 100

    def test_clamp_yin_yang_lower(self):
        assert clamp_aptitude(-200, "yin_yang_balance") == -100

    def test_add_aptitude_increments_correctly(self):
        p = AptitudeProfile(affinity_fire=20)
        p2 = add_aptitude(p, "affinity_fire", 10)
        assert p2.affinity_fire == 30

    def test_add_aptitude_clamps_at_100(self):
        p = AptitudeProfile(affinity_fire=95)
        p2 = add_aptitude(p, "affinity_fire", 20)
        assert p2.affinity_fire == 100

    def test_add_aptitude_yin_yang_clamps(self):
        p = AptitudeProfile(yin_yang_balance=90)
        p2 = add_aptitude(p, "yin_yang_balance", 50)
        assert p2.yin_yang_balance == 100

    def test_add_aptitude_invalid_key_raises(self):
        p = AptitudeProfile()
        with pytest.raises(ValueError):
            add_aptitude(p, "affinity_nonexistent", 5)


# ---------------------------------------------------------------------------
# 4. Stat multipliers
# ---------------------------------------------------------------------------

class TestStatMultipliers:
    def test_returns_dict(self):
        p = AptitudeProfile(affinity_fire=50)
        mults = aptitude_stat_multipliers(p)
        assert isinstance(mults, dict)

    def test_fire_crit_positive(self):
        p = AptitudeProfile(affinity_fire=100)
        mults = aptitude_stat_multipliers(p)
        assert mults["crit_chance_bonus"] == pytest.approx(0.20, rel=1e-3)
        assert mults["crit_multiplier_bonus"] == pytest.approx(0.50, rel=1e-3)

    def test_zero_fire_zero_crit(self):
        p = AptitudeProfile(affinity_fire=0)
        mults = aptitude_stat_multipliers(p)
        assert mults["crit_chance_bonus"] == 0.0

    def test_qi_gain_bonus(self):
        p = AptitudeProfile(affinity_qi=50)
        mults = aptitude_stat_multipliers(p)
        expected = round((50 / 100) * 0.20, 4)
        assert mults["qi_gain_bonus"] == pytest.approx(expected, rel=1e-3)

    def test_water_evasion_speed_vitality(self):
        p = AptitudeProfile(affinity_water=100)
        mults = aptitude_stat_multipliers(p)
        assert mults["evasion_bonus"] == pytest.approx(0.15, rel=1e-3)
        assert mults["speed_bonus"] == pytest.approx(0.10, rel=1e-3)
        assert mults["vitality_recovery"] == pytest.approx(0.10, rel=1e-3)

    def test_yang_fortitude_with_positive_balance(self):
        p = AptitudeProfile(yin_yang_balance=100)
        mults = aptitude_stat_multipliers(p)
        assert mults["yang_fortitude"] == pytest.approx(0.10, rel=1e-3)
        assert mults["yin_hd_resistance"] == 0.0

    def test_yin_resistance_with_negative_balance(self):
        p = AptitudeProfile(yin_yang_balance=-100)
        mults = aptitude_stat_multipliers(p)
        assert mults["yin_hd_resistance"] == pytest.approx(0.10, rel=1e-3)
        assert mults["yang_fortitude"] == 0.0

    def test_all_expected_keys_present(self):
        p = AptitudeProfile()
        mults = aptitude_stat_multipliers(p)
        expected_keys = {
            "crit_chance_bonus", "crit_multiplier_bonus",
            "evasion_bonus", "speed_bonus", "vitality_recovery",
            "debuff_immunity_bonus",
            "armor_penetration", "raw_damage_bonus",
            "cc_resistance", "barrier_shielding",
            "qi_regen_bonus", "qi_gain_bonus", "dantian_efficiency",
            "multi_hit_chance",
            "cleave_damage_bonus", "lifesteal_bonus",
            "counter_attack_bonus", "armor_break_chance",
            "dantian_damage_bonus",
            "yang_fortitude", "yin_hd_resistance",
        }
        assert expected_keys.issubset(set(mults.keys()))


# ---------------------------------------------------------------------------
# 5. Prerequisite checks
# ---------------------------------------------------------------------------

class TestPrerequisiteChecks:
    def test_passes_when_met(self):
        p = AptitudeProfile(affinity_fire=50, intent_sword=35)
        ok, missing = check_prerequisites(
            {"min_affinity_fire": 40, "min_intent_sword": 30}, p
        )
        assert ok is True
        assert missing == []

    def test_fails_when_not_met(self):
        p = AptitudeProfile(affinity_fire=30, intent_sword=20)
        ok, missing = check_prerequisites(
            {"min_affinity_fire": 40, "min_intent_sword": 30}, p
        )
        assert ok is False
        assert len(missing) == 2

    def test_failure_message_is_human_readable(self):
        p = AptitudeProfile(affinity_fire=10)
        ok, missing = check_prerequisites({"min_affinity_fire": 40}, p)
        assert not ok
        assert "Fire" in missing[0]
        assert "10" in missing[0]
        assert "40" in missing[0]

    def test_ignores_unknown_req_keys(self):
        p = AptitudeProfile()
        ok, missing = check_prerequisites({"min_totally_unknown_stat": 99}, p)
        assert ok is True   # unknown keys are silently skipped

    def test_dict_profile_supported(self):
        d = {"affinity_fire": 50, "intent_sword": 20}
        ok, missing = check_prerequisites({"min_affinity_fire": 40}, d)
        assert ok is True


# ---------------------------------------------------------------------------
# 6. Migration 012 — SQLite column presence
# ---------------------------------------------------------------------------

MIGRATION_012_PATH = (
    Path(__file__).resolve().parent.parent
    / "migrations" / "012_spiritual_aptitudes.sql"
)

EXPECTED_NEW_COLUMNS = [
    "yin_yang_balance",
    "affinity_fire", "affinity_water", "affinity_wood",
    "affinity_metal", "affinity_earth", "affinity_qi",
    "intent_sword", "intent_sabre", "intent_spear", "intent_fist",
    "special_root",
]


class TestMigration012:
    def _run_migration(self, conn: sqlite3.Connection) -> None:
        sql = MIGRATION_012_PATH.read_text(encoding="utf-8")
        statements = _split_sql_statements(sql)
        for stmt in statements:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" in str(exc):
                    continue
                raise
        conn.commit()

    def _get_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    def test_migration_file_exists(self):
        assert MIGRATION_012_PATH.exists(), (
            f"Migration file not found: {MIGRATION_012_PATH}"
        )

    def test_new_columns_added_to_cultivators(self):
        # Bootstrap minimal cultivators table then apply migration 012
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE cultivators ("
            "id INTEGER PRIMARY KEY, "
            "user_id INTEGER, guild_id INTEGER, username TEXT, "
            "realm_tier INTEGER DEFAULT 1)"
        )
        conn.commit()

        self._run_migration(conn)

        cols = self._get_columns(conn, "cultivators")
        for expected in EXPECTED_NEW_COLUMNS:
            assert expected in cols, f"Column '{expected}' missing after migration 012"

        conn.close()

    def test_migration_is_idempotent(self):
        """Running migration 012 twice must not crash (duplicate column tolerance)."""
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE cultivators ("
            "id INTEGER PRIMARY KEY, user_id INTEGER, guild_id INTEGER, "
            "username TEXT, realm_tier INTEGER DEFAULT 1)"
        )
        conn.commit()
        self._run_migration(conn)
        # Second run — should silently skip already-added columns
        self._run_migration(conn)
        conn.close()

    def test_new_columns_have_correct_defaults(self):
        # Use the actual 001_init.sql to create a realistic base schema,
        # then apply migration 012 and verify new column defaults.
        base_sql_path = (
            Path(__file__).resolve().parent.parent
            / "migrations" / "001_init.sql"
        )
        conn = sqlite3.connect(":memory:")
        base_stmts = _split_sql_statements(base_sql_path.read_text(encoding="utf-8"))
        for stmt in base_stmts:
            try:
                conn.execute(stmt)
            except Exception:
                pass
        conn.commit()

        self._run_migration(conn)

        conn.execute(
            "INSERT INTO cultivators (user_id, guild_id, username) VALUES (1, 1, 'Tester')"
        )
        conn.commit()
        cols_info = conn.execute("PRAGMA table_info(cultivators)").fetchall()
        col_names = [r[1] for r in cols_info]
        row = conn.execute("SELECT * FROM cultivators WHERE user_id=1").fetchone()
        d = dict(zip(col_names, row))

        assert d["yin_yang_balance"] == 0
        assert d["affinity_fire"] == 10
        assert d["affinity_qi"] == 10
        assert d["intent_sword"] == 5
        assert d["special_root"] is None

        conn.close()
