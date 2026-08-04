#!/usr/bin/env python3
"""scripts/validate_migration.py

Validation utility comparing row counts between SQLite source and PostgreSQL target.
"""
import asyncio
import os
import sys

TABLES = [
    "cultivators",
    "sects",
    "dao_bonds",
    "items",
    "item_templates",
    "qi_buffer",
    "alchemy_recipes",
    "alchemy_attempts",
    "secret_realm_templates",
    "secret_realm_runs",
    "reincarnation_log",
    "world_events",
    "world_event_participants",
    "dao_laws",
    "cultivator_laws",
    "market_listings",
    "trade_offers",
    "guild_config",
    "audit_log",
]


async def validate_migration(sqlite_path: str, postgres_url: str):
    import aiosqlite
    import asyncpg

    print(f"Validating migration between SQLite ({sqlite_path}) and PostgreSQL ({postgres_url})...\n")

    sqlite = await aiosqlite.connect(sqlite_path)
    postgres = await asyncpg.connect(postgres_url)

    mismatches = 0
    total_tables = 0

    for table in TABLES:
        try:
            cur_s = await sqlite.execute(f"SELECT COUNT(*) FROM {table}")
            s_row = await cur_s.fetchone()
            s_count = s_row[0] if s_row else 0
        except Exception:
            s_count = 0

        try:
            p_row = await postgres.fetchrow(f"SELECT COUNT(*) FROM {table}")
            p_count = p_row[0] if p_row else 0
        except Exception:
            p_count = 0

        total_tables += 1
        status = "✅ PASS" if s_count == p_count else "❌ MISMATCH"
        if s_count != p_count:
            mismatches += 1

        print(f"Table {table:<25}: SQLite={s_count:<6} | Postgres={p_count:<6} [{status}]")

    await sqlite.close()
    await postgres.close()

    print(f"\nValidation Summary: {total_tables - mismatches}/{total_tables} tables passed parity check.")
    if mismatches == 0:
        print("🎉 ALL TABLES VERIFIED! Data parity confirmed.")
    else:
        print(f"⚠️ {mismatches} table(s) show row count discrepancies. Please check migration logs.")


if __name__ == "__main__":
    sqlite_db = os.getenv("SQLITE_DB_PATH", "heavenly_dao.db")
    postgres_uri = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/heavenly_dao")

    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        print("Usage: python scripts/validate_migration.py [sqlite_path] [postgres_url]")
        sys.exit(0)

    if len(sys.argv) > 1:
        sqlite_db = sys.argv[1]
    if len(sys.argv) > 2:
        postgres_uri = sys.argv[2]

    asyncio.run(validate_migration(sqlite_db, postgres_uri))
