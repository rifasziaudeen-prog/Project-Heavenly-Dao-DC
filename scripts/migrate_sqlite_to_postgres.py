#!/usr/bin/env python3
"""scripts/migrate_sqlite_to_postgres.py

Automated one-way data migration from SQLite to PostgreSQL.
Deserializes SQLite JSON text fields to native PostgreSQL JSONB payloads.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

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


async def migrate_data(sqlite_path: str, postgres_url: str):
    import aiosqlite
    import asyncpg

    print(f"Connecting to SQLite database: {sqlite_path}")
    sqlite = await aiosqlite.connect(sqlite_path)

    print(f"Connecting to PostgreSQL database: {postgres_url}")
    postgres = await asyncpg.connect(postgres_url)

    await postgres.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    for table in TABLES:
        try:
            print(f"Migrating table: {table}...")
            cursor = await sqlite.execute(f"SELECT * FROM {table}")
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            if not rows:
                print(f"  -> {table}: 0 rows, skipping.")
                continue

            placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
            col_str = ", ".join(columns)
            query = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

            converted_rows = []
            for row in rows:
                converted = []
                for val in row:
                    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                        try:
                            converted.append(json.loads(val))
                        except Exception:
                            converted.append(val)
                    else:
                        converted.append(val)
                converted_rows.append(converted)

            await postgres.executemany(query, converted_rows)
            print(f"  -> {table}: successfully migrated {len(rows)} rows!")
        except Exception as err:
            print(f"  -> {table}: migration error or table missing in SQLite: {err}")

    await sqlite.close()
    await postgres.close()
    print("\n✅ SQLite to PostgreSQL migration complete!")


if __name__ == "__main__":
    sqlite_db = os.getenv("SQLITE_DB_PATH", "heavenly_dao.db")
    postgres_uri = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/heavenly_dao")
    
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        print("Usage: python scripts/migrate_sqlite_to_postgres.py [sqlite_path] [postgres_url]")
        sys.exit(0)

    if len(sys.argv) > 1:
        sqlite_db = sys.argv[1]
    if len(sys.argv) > 2:
        postgres_uri = sys.argv[2]

    asyncio.run(migrate_data(sqlite_db, postgres_uri))
