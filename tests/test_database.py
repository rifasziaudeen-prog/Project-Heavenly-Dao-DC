"""Tests for the crash-atomic transaction helper (db/database.py).

Covers: success commits all, exception rolls back all (the same guarantee
SQLite delivers on process death), nested savepoints (inner failure keeps the
outer block alive), and the cross-task guard that stops a background loop's
write from being absorbed into another task's open transaction.
"""
import asyncio
import sqlite3
import tempfile
from pathlib import Path

from db.database import Database, run_migrations


def _fresh_db() -> tuple[Database, Path]:
    d = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db = Database(Path(d.name) / "tx.db")
    return db, d


async def _seed(db: Database) -> None:
    await run_migrations(db)
    await db.execute(
        "INSERT INTO cultivators (user_id, guild_id, username) VALUES (?,?,?)",
        (111, 1, "seed"),
    )


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- commit path
def test_transaction_commits_all_statements_as_one_unit():
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            async with db.transaction():
                await db.execute(
                    "UPDATE cultivators SET username=?, luck=? WHERE user_id=?",
                    ("after", 42, 111),
                )
                await db.execute(
                    "UPDATE cultivators SET spirit=? WHERE user_id=?",
                    (99, 111),
                )
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["username"] == "after"
            assert row["luck"] == 42
            assert row["spirit"] == 99
        finally:
            await db.close()
            d.cleanup()

    _run(main())


# -------------------------------------------------------------- rollback path
def test_transaction_rolls_back_everything_on_exception():
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            with_exc = False
            try:
                async with db.transaction():
                    await db.execute(
                        "UPDATE cultivators SET username=? WHERE user_id=?",
                        ("partial", 111),
                    )
                    await db.execute(
                        "UPDATE cultivators SET luck=? WHERE user_id=?",
                        (999, 111),
                    )
                    raise RuntimeError("boom mid-sequence")
            except RuntimeError:
                with_exc = True
            assert with_exc
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["username"] == "seed"   # neither write persisted
            assert row["luck"] == 5            # untouched
        finally:
            await db.close()
            d.cleanup()

    _run(main())


# ------------------------------------------------------------------ crash test
def test_open_transaction_is_lost_on_abrupt_close_like_a_crash():
    """An uncommitted transaction vanishes when the connection dies — the exact
    guarantee a rollback reproduces (SQLite rolls back open transactions on
    close, which is what process death does too)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = Path(d) / "crash.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("BEGIN")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.close()  # no COMMIT -> implicit rollback, like a crash

        conn2 = sqlite3.connect(path)
        try:
            count = conn2.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert count == 0
        finally:
            conn2.close()


def test_mid_transaction_crash_leaves_no_partial_state():
    """Rollback after a mid-block exception is the crash path — prove nothing
    partial survives."""
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            # Two independent blocks: first commits, second dies — the second
            # must not leak anything, including its uncommitted row.
            async with db.transaction():
                await db.execute(
                    "UPDATE cultivators SET username=? WHERE user_id=?",
                    ("first", 111),
                )
            try:
                async with db.transaction():
                    await db.execute(
                        "UPDATE cultivators SET username=? WHERE user_id=?",
                        ("second", 111),
                    )
                    await db.execute(
                        "INSERT INTO cultivators (user_id, guild_id, username)"
                        " VALUES (?,?,?)", (222, 1, "ghost"),
                    )
                    raise KeyboardInterrupt  # BaseException, not just Exception
            except KeyboardInterrupt:
                pass
            first = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            ghost = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (222,))
            assert first["username"] == "first"
            assert ghost is None
        finally:
            await db.close()
            d.cleanup()

    _run(main())


# ------------------------------------------------------------------ nesting
def test_nested_inner_rollback_preserves_outer_block():
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            async with db.transaction():
                await db.execute(
                    "UPDATE cultivators SET username=? WHERE user_id=?",
                    ("outer", 111),
                )
                try:
                    async with db.transaction():
                        await db.execute(
                            "UPDATE cultivators SET luck=? WHERE user_id=?",
                            (777, 111),
                        )
                        raise ValueError("inner boom")
                except ValueError:
                    pass
                # Outer block still alive; add another write after the inner
                # failure to prove the transaction survived.
                await db.execute(
                    "UPDATE cultivators SET spirit=? WHERE user_id=?",
                    (50, 111),
                )
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["username"] == "outer"
            assert row["spirit"] == 50       # written after inner rollback
            assert row["luck"] == 5          # inner write rolled back
        finally:
            await db.close()
            d.cleanup()

    _run(main())


def test_nested_inner_success_commits_with_outer():
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            async with db.transaction():
                await db.execute(
                    "UPDATE cultivators SET username=? WHERE user_id=?",
                    ("outer", 111),
                )
                async with db.transaction():
                    await db.execute(
                        "UPDATE cultivators SET luck=? WHERE user_id=?",
                        (33, 111),
                    )
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["username"] == "outer"
            assert row["luck"] == 33
        finally:
            await db.close()
            d.cleanup()

    _run(main())


# --------------------------------------------------------------- cross-task
def test_other_task_write_waits_and_is_not_absorbed_by_rollback():
    """A background write (sweep loop, regen loop) issued while another task
    holds an open transaction must NOT join it — if the transaction rolls
    back, the background write still lands afterwards."""
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            tx_entered = asyncio.Event()
            tx_release = asyncio.Event()

            async def tx_worker() -> None:
                try:
                    async with db.transaction():
                        await db.execute(
                            "UPDATE cultivators SET username=? WHERE user_id=?",
                            ("tx", 111),
                        )
                        tx_entered.set()
                        await tx_release.wait()
                        raise RuntimeError("tx dies")
                except RuntimeError:
                    pass

            task = asyncio.create_task(tx_worker())
            await tx_entered.wait()
            other = asyncio.create_task(
                db.execute(
                    "UPDATE cultivators SET username=? WHERE user_id=?",
                    ("bg", 111),
                )
            )
            await asyncio.sleep(0.05)          # bg write is now blocked on lock
            assert not other.done()
            tx_release.set()
            await task
            await other                          # lands only AFTER tx commits/rolls back
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["username"] == "bg"       # tx's "tx" write is gone, bg's survives
        finally:
            await db.close()
            d.cleanup()

    _run(main())


def test_other_task_write_waits_for_commit_not_absorbed():
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            tx_entered = asyncio.Event()
            tx_release = asyncio.Event()

            async def tx_worker() -> None:
                async with db.transaction():
                    await db.execute(
                        "UPDATE cultivators SET username=? WHERE user_id=?",
                        ("tx", 111),
                    )
                    tx_entered.set()
                    await tx_release.wait()

            task = asyncio.create_task(tx_worker())
            await tx_entered.wait()
            other = asyncio.create_task(
                db.execute(
                    "UPDATE cultivators SET username=? WHERE user_id=?",
                    ("bg", 111),
                )
            )
            await asyncio.sleep(0.05)
            tx_release.set()
            await task
            await other
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["username"] == "bg"       # bg ran after the commit
        finally:
            await db.close()
            d.cleanup()

    _run(main())


# ------------------------------------------- auto-commit still works outside
def test_auto_commit_unchanged_outside_transactions():
    async def main() -> None:
        db, d = _fresh_db()
        await db.connect()
        try:
            await _seed(db)
            await db.execute(
                "UPDATE cultivators SET username=? WHERE user_id=?",
                ("plain", 111),
            )
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["username"] == "plain"
            # executemany path too
            await db.executemany(
                "UPDATE cultivators SET luck=? WHERE user_id=?",
                [(7, 111), (8, 111)],
            )
            row = await db.fetchone("SELECT * FROM cultivators WHERE user_id=?", (111,))
            assert row["luck"] == 8
        finally:
            await db.close()
            d.cleanup()

    _run(main())
