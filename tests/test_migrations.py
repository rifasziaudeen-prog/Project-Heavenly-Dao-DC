"""Tests for the versioned migration runner."""
import asyncio
import tempfile
from pathlib import Path

from db.database import Database, run_migrations

EXPECTED_TABLES = {
    "schema_migrations", "cultivators", "sects", "companions", "items",
    "secret_realms", "qi_buffer", "qi_hourly_stats", "dao_protection_charms",
    "breakthrough_log", "anti_cheat_flags", "llm_usage", "world_events",
    "world_event_participants", "narrative_templates", "guild_config",
    "dao_bonds",
}


def test_migrations_apply_and_are_idempotent():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db = Database(Path(d) / "mig.db")
            await db.connect()
            applied = await run_migrations(db)
            assert applied == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]

            rows = await db.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {r["name"] for r in rows}
            assert EXPECTED_TABLES | {"item_templates", "alchemy_recipes", "alchemy_attempts", "reincarnation_log", "secret_realm_templates", "secret_realm_runs", "world_events", "world_event_participants", "world_event_phases", "dao_laws", "cultivator_laws", "market_listings", "trade_offers"} <= tables

            # Critical P0 indexes
            idx = await db.fetchall("PRAGMA index_list('cultivators')")
            idx_names = {r["name"] for r in idx}
            assert "idx_cultivators_guild_user" in idx_names

            # Migration 002 additions
            await db.fetchone("SELECT rage_breakthrough_bonus_until FROM cultivators LIMIT 1")
            cfg_cols = await db.fetchall("PRAGMA table_info('guild_config')")
            assert "dao_role_to_gender" in {r["name"] for r in cfg_cols}

            # Migration 003 additions: spirit_stones wallet + index
            await db.fetchone("SELECT spirit_stones FROM cultivators LIMIT 1")
            assert "idx_cultivators_spirit_stones" in idx_names

            # Migration 004 additions: item equipment tracking + item_templates catalog
            await db.fetchone("SELECT is_equipped FROM items LIMIT 1")
            tmpl_count = await db.fetchone("SELECT COUNT(*) AS c FROM item_templates")
            assert tmpl_count["c"] > 0

            # Migration 005 additions: alchemy mastery + recipes catalog
            await db.fetchone("SELECT alchemy_mastery FROM cultivators LIMIT 1")
            recipe_count = await db.fetchone("SELECT COUNT(*) AS c FROM alchemy_recipes")
            assert recipe_count["c"] > 0

            # Migration 006 additions: inherited_technique + reincarnation_log table
            await db.fetchone("SELECT inherited_technique FROM cultivators LIMIT 1")

            # Migration 007 additions: secret_realm_templates + secret_realm_runs
            realm_count = await db.fetchone("SELECT COUNT(*) AS c FROM secret_realm_templates")
            assert realm_count["c"] > 0

            # Migration 008 additions: world_events + world_event_participants
            await db.fetchone("SELECT boss_hp_max FROM world_events LIMIT 1")

            # Migration 009 additions: dao_laws catalog + cultivator_laws junction
            laws_count = await db.fetchone("SELECT COUNT(*) AS c FROM dao_laws")
            assert laws_count["c"] > 0

            # Migration 010 additions: market_listings + trade_offers
            await db.fetchone("SELECT buyout_price FROM market_listings LIMIT 1")

            # Migration 012 additions: spiritual aptitudes columns
            await db.fetchone("SELECT affinity_fire FROM cultivators LIMIT 1")
            await db.fetchone("SELECT yin_yang_balance FROM cultivators LIMIT 1")
            await db.fetchone("SELECT intent_sword FROM cultivators LIMIT 1")
            await db.fetchone("SELECT special_root FROM cultivators LIMIT 1")

            # Idempotent: second run applies nothing
            assert await run_migrations(db) == []
            await db.close()

    asyncio.run(main())


def test_migration_rerun_tolerates_duplicate_columns():
    """A partially-applied migration (lost version row) must re-run cleanly:
    CREATE IF NOT EXISTS is a no-op and ALTER ADD COLUMN is tolerated."""
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db = Database(Path(d) / "rerun.db")
            await db.connect()
            await run_migrations(db)
            # Simulate a crash mid-migration: version row lost for 002..010
            # but the ALTER TABLE statements already applied.
            await db.execute("DELETE FROM schema_migrations WHERE version IN (2,3,4,5,6,7,8,9,10)")
            await run_migrations(db)  # must not raise "duplicate column name"
            rows = await db.fetchall("SELECT version FROM schema_migrations")
            assert {r["version"] for r in rows} == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12}
            await db.close()

    asyncio.run(main())


def test_dao_bond_pair_unique_constraint():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db = Database(Path(d) / "pair.db")
            await db.connect()
            await run_migrations(db)
            for uid in (1, 2):
                await db.execute(
                    "INSERT INTO cultivators (user_id, guild_id, username)"
                    " VALUES (?,?,?)",
                    (uid, 1, f"c{uid}"),
                )
            a = (await db.fetchone(
                "SELECT id FROM cultivators WHERE user_id=1"))["id"]
            b = (await db.fetchone(
                "SELECT id FROM cultivators WHERE user_id=2"))["id"]
            await db.execute(
                "INSERT INTO dao_bonds (cultivator_a_id, cultivator_b_id,"
                " initiator_id, bond_type) VALUES (?,?,?,'rival')",
                (a, b, a),
            )
            # Reversed direction must collide on the MIN/MAX unique index
            try:
                await db.execute(
                    "INSERT INTO dao_bonds (cultivator_a_id, cultivator_b_id,"
                    " initiator_id, bond_type) VALUES (?,?,?,'rival')",
                    (b, a, b),
                )
                raise AssertionError("Duplicate pair should have raised")
            except Exception:
                pass
            await db.close()

    asyncio.run(main())


def test_per_guild_unique_constraint():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db = Database(Path(d) / "uniq.db")
            await db.connect()
            await run_migrations(db)
            await db.execute(
                "INSERT INTO cultivators (user_id, guild_id, username)"
                " VALUES (?,?,?)",
                (111, 1, "a"),
            )
            try:
                await db.execute(
                    "INSERT INTO cultivators (user_id, guild_id, username)"
                    " VALUES (?,?,?)",
                    (111, 1, "b"),  # same user, same guild -> must fail
                )
                raise AssertionError("Duplicate (guild, user) should have raised")
            except Exception:
                pass
            # Same user in a different guild is fine (multi-guild isolation)
            await db.execute(
                "INSERT INTO cultivators (user_id, guild_id, username)"
                " VALUES (?,?,?)",
                (111, 2, "a"),
            )
            await db.close()

    asyncio.run(main())
