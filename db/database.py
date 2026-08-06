"""Async SQLite access layer.

* Single aiosqlite connection (SQLite is single-writer; WAL mode gives
  concurrent readers and keeps writes fast).
* Versioned migration runner (`migrations/*.sql`).
* Native aiosqlite backup for the daily snapshot.
* Crash-atomic write blocks via `Database.transaction()` (BEGIN / COMMIT /
  ROLLBACK) — multi-step flows like /buy, reincarnation, and duel payouts
  commit as one unit or not at all.

All game-logic queries live in the cogs / core modules; this module only
provides plumbing so the migration path to PostgreSQL (see MIGRATION.md)
stays confined to a few query functions.
"""
from __future__ import annotations

import asyncio
import re
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
import aiosqlite.core as _aiosqlite_core

from config import default as config


class _DaemonAiosqliteThread(threading.Thread):
    """aiosqlite spawns its per-connection worker thread NON-daemon, which keeps
    the whole process alive forever whenever a connection is left unclosed
    (Ctrl+C on the bot, or a test that failed before its teardown). Daemonizing
    the thread means an unclean exit can never wedge the process — SQLite's own
    WAL/journal crash-recovery handles any in-flight write on next open.
    """

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("daemon", True)
        super().__init__(*args, **kwargs)


_aiosqlite_core.Thread = _DaemonAiosqliteThread

_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class _ReentrantAsyncLock:
    """asyncio.Lock that the owning task can re-acquire without deadlocking.

    The transaction helper holds the write lock across its whole block, and
    the block's own statements must still be able to run — so a plain
    asyncio.Lock would deadlock on nested transactions. This tracks the
    owning task and a re-entry count: the owner passes through instantly,
    any OTHER task blocks until the owner releases (protecting the open
    transaction from absorbed writes).
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task | None = None
        self._count = 0

    async def acquire(self) -> None:
        task = asyncio.current_task()
        if task is self._owner:
            self._count += 1
            return
        await self._lock.acquire()
        self._owner = task
        self._count = 1

    def release(self) -> None:
        task = asyncio.current_task()
        if task is not self._owner:
            raise RuntimeError("reentrant lock released by a non-owner task")
        self._count -= 1
        if self._count == 0:
            self._owner = None
            self._lock.release()


class Database:
    """Thin async wrapper around a single aiosqlite connection."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.conn: aiosqlite.Connection | None = None
        # Transaction bookkeeping: `_tx_depth > 0` means a transaction (or
        # nested savepoint) is open on this single connection. The reentrant
        # lock serializes writers so another task's statement can never be
        # absorbed into (and silently rolled back with) a transaction it
        # doesn't own.
        self._tx_lock = _ReentrantAsyncLock()
        self._tx_depth = 0

    @asynccontextmanager
    async def _tx_guard(self):
        """Reentrant write lock: same task passes through, others wait."""
        await self._tx_lock.acquire()
        try:
            yield
        finally:
            self._tx_lock.release()

    # -- lifecycle -----------------------------------------------------------
    async def connect(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.execute("PRAGMA busy_timeout=5000")
        await self.conn.commit()
        # Fold any uncheckpointed WAL (from a previous ungraceful shutdown)
        # back into the main database file. Safe: TRUNCATE returns busy (with
        # the busy_timeout) if another connection holds the database.
        await self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    # -- helpers -------------------------------------------------------------
    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        assert self.conn is not None, "Database not connected"
        async with self._tx_guard():
            cursor = await self.conn.execute(sql, params)
            if self._tx_depth == 0:
                # Auto-commit ONLY outside a transaction; inside one, the
                # owning block's transaction() issues the single
                # COMMIT/ROLLBACK.
                await self.conn.commit()
            return cursor

    async def executemany(self, sql: str, seq: list[tuple]) -> None:
        assert self.conn is not None, "Database not connected"
        async with self._tx_guard():
            await self.conn.executemany(sql, seq)
            if self._tx_depth == 0:
                await self.conn.commit()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["Database"]:
        """Crash-atomic write block (BEGIN / COMMIT / ROLLBACK).

        Usage:
            async with db.transaction():
                await db.execute(...)
                await db.execute(...)

        * Success commits every statement as ONE unit.
        * ANY exception rolls everything back, then re-raises.
        * Nested blocks become SAVEPOINTs, so an inner block's failure rolls
          back only itself — the outer transaction survives.
        * While a block is open, `execute`/`executemany` skip auto-commit and
          other tasks' writes wait on the reentrant lock instead of joining
          the block.
        * Rule of the road: read what you need BEFORE the block, and do NOT
          await Discord (views, sends) inside it — the write lock is held for
          the block's whole duration.
        """
        assert self.conn is not None, "Database not connected"
        async with self._tx_guard():
            if self._tx_depth:
                name = f"hdao_sp{self._tx_depth}"
                await self.conn.execute(f"SAVEPOINT {name}")
                self._tx_depth += 1
                try:
                    yield self
                except BaseException:
                    await self.conn.execute(f"ROLLBACK TO {name}")
                    raise
                finally:
                    await self.conn.execute(f"RELEASE {name}")
                    self._tx_depth -= 1
            else:
                await self.conn.execute("BEGIN")
                self._tx_depth += 1
                try:
                    yield self
                except BaseException:
                    await self.conn.rollback()
                    raise
                else:
                    try:
                        await self.conn.commit()
                    except BaseException:
                        # A failed COMMIT leaves the transaction OPEN — roll it
                        # back so the connection is never left holding a live
                        # transaction that a later auto-commit could silently
                        # commit as if it had succeeded.
                        await self.conn.rollback()
                        raise
                finally:
                    self._tx_depth -= 1

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
