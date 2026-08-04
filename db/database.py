"""Async SQLite access layer.

* Single aiosqlite connection (SQLite is single-writer; WAL mode gives
  concurrent readers and keeps writes fast).
* Versioned migration runner (`migrations/*.sql`).
* Native aiosqlite backup for the daily snapshot.

All game-logic queries live in the cogs / core modules; this module only
provides plumbing so the migration path to PostgreSQL (see MIGRATION.md)
stays confined to a few query functions.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import aiosqlite

from config import default as config

_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class Database:
    """Thin async wrapper around a single aiosqlite connection."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.conn: aiosqlite.Connection | None = None

    # -- lifecycle -----------------------------------------------------------
    async def connect(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.execute("PRAGMA busy_timeout=5000")
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    # -- helpers -------------------------------------------------------------
    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        assert self.conn is not None, "Database not connected"
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor

    async def executemany(self, sql: str, seq: list[tuple]) -> None:
        assert self.conn is not None, "Database not connected"
        await self.conn.executemany(sql, seq)
        await self.conn.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        assert self.conn is not None, "Database not connected"
        cursor = await self.conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        assert self.conn is not None, "Database not connected"
        cursor = await self.conn.execute(sql, params)
        return await cursor.fetchall()

    async def backup_to(self, dest_path: str | Path) -> None:
        """Online backup via the SQLite backup API (safe with WAL)."""
        assert self.conn is not None, "Database not connected"
        dest = await aiosqlite.connect(str(dest_path))
        try:
            await self.conn.backup(dest)
        finally:
            await dest.close()


def _split_sql_statements(sql: str) -> list[str]:
    """Split a migration file into individual statements.

    `--` comments are stripped first (they carry no SQL meaning) so a
    semicolon inside a comment — e.g. "(soft ref; circular FK)" — cannot
    chop a statement in half.
    """
    lines = [line.split("--", 1)[0] if "--" in line else line for line in sql.splitlines()]
    cleaned = "\n".join(lines)
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]


async def run_migrations(db: Database, migrations_dir: Path | None = None) -> list[int]:
    """Apply pending `NNN_*.sql` migrations in version order (idempotent).

    Statements run one at a time. SQLite has no `ALTER TABLE ADD COLUMN IF NOT
    EXISTS`, so a re-run after a partially-applied file tolerates
    "duplicate column name" errors (the column already exists) — preserving the
    self-healing contract 001 established with CREATE TABLE IF NOT EXISTS.
    """
    assert db.conn is not None, "Database not connected"
    await db.conn.execute(_SCHEMA_MIGRATIONS)
    await db.conn.commit()

    applied = {
        row["version"]
        for row in await db.fetchall("SELECT version FROM schema_migrations")
    }

    directory = migrations_dir or config.MIGRATIONS_DIR
    files = sorted(
        p for p in directory.glob("*.sql") if re.match(r"^\d+_", p.name)
    )
    newly_applied: list[int] = []
    for path in files:
        version = int(path.name.split("_", 1)[0])
        if version in applied:
            continue
        for statement in _split_sql_statements(path.read_text(encoding="utf-8")):
            try:
                await db.conn.execute(statement)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" in str(exc):
                    continue  # column already added by a partial earlier run
                raise
        await db.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
        )
        newly_applied.append(version)
    return newly_applied


async def backup_database(
    db: Database, backup_dir: Path | None = None, name: str | None = None
) -> Path | None:
    """Snapshot the DB to `backup_dir/heavenly_dao_YYYY-MM-DD.db` (skip if exists)."""
    directory = backup_dir or config.BACKUP_DIR
    directory.mkdir(parents=True, exist_ok=True)
    if name is None:
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        name = f"heavenly_dao_{stamp}.db"
    dest = directory / name
    if dest.exists():
        return None
    await db.backup_to(dest)
    return dest
