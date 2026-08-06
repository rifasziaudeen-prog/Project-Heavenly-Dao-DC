"""Tests for the v1.16.0 hot-path caches (bot/main.py).

Guild config is cached in memory (invalidate-on-write + TTL), as are the
sect array level and active companions. Together they cut the passive-Qi
per-message path from ~5 DB round-trips to 2 (cultivator read + quota write).
"""
import asyncio
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from bot.main import HeavenlyDaoBot
from config import default as config
from db.queries import get_or_create_cultivator


async def _bot_with_db(temp_path: Path) -> HeavenlyDaoBot:
    bot = HeavenlyDaoBot()
    bot.db.path = str(temp_path / "cache.db")
    await bot.db.connect()
    from db.database import run_migrations

    await run_migrations(bot.db)
    return bot


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------- guild config
def test_guild_config_warm_cache_makes_zero_db_calls(monkeypatch):
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                first = await bot._guild_config(1)      # SELECT (miss) + INSERT
                assert first["guild_id"] == 1

                # Second call must hit the cache: zero fetches, zero writes.
                counts = {"fetch": 0, "exec": 0}
                real_fetch, real_exec = bot.db.fetchone, bot.db.execute

                async def spy_fetch(sql, params=()):
                    counts["fetch"] += 1
                    return await real_fetch(sql, params)

                async def spy_exec(sql, params=()):
                    counts["exec"] += 1
                    return await real_exec(sql, params)

                monkeypatch.setattr(bot.db, "fetchone", spy_fetch)
                monkeypatch.setattr(bot.db, "execute", spy_exec)

                again = await bot._guild_config(1)
                assert again == first
                assert counts["fetch"] == 0
                assert counts["exec"] == 0
            finally:
                await bot.db.close()

    _run(main())


def test_guild_config_returns_copies_not_cache_references(monkeypatch):
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                await bot._guild_config(1)
                got = await bot._guild_config(1)
                got["xianxia_terms_language"] = "HACKED"
                again = await bot._guild_config(1)
                assert again["xianxia_terms_language"] == "bilingual"
            finally:
                await bot.db.close()

    _run(main())


def test_guild_config_invalidate_on_write_forces_refetch(monkeypatch):
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                await bot._guild_config(1)
                await bot.db.execute(
                    "UPDATE guild_config SET erasure_enabled=0 WHERE guild_id=?", (1,),
                )
                bot._invalidate_guild_config(1)   # what /dao_config now does

                counts = {"fetch": 0}
                real_fetch = bot.db.fetchone

                async def spy_fetch(sql, params=()):
                    counts["fetch"] += 1
                    return await real_fetch(sql, params)

                monkeypatch.setattr(bot.db, "fetchone", spy_fetch)
                fresh = await bot._guild_config(1)
                assert counts["fetch"] == 1        # re-read from the DB
                assert fresh["erasure_enabled"] == 0
            finally:
                await bot.db.close()

    _run(main())


def test_guild_config_ttl_expiry_self_heals(monkeypatch):
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                await bot._guild_config(1)
                # Age the entry past the TTL (simulating an out-of-band write
                # the bot couldn't invalidate — e.g. the setup script).
                entry = bot._guild_configs[1]
                bot._guild_configs[1] = (time.monotonic() - config.CACHE_TTL_SECONDS - 5, entry[1])

                counts = {"fetch": 0}
                real_fetch = bot.db.fetchone

                async def spy_fetch(sql, params=()):
                    counts["fetch"] += 1
                    return await real_fetch(sql, params)

                monkeypatch.setattr(bot.db, "fetchone", spy_fetch)
                await bot._guild_config(1)
                assert counts["fetch"] == 1        # expired -> re-read
            finally:
                await bot.db.close()

    _run(main())


# ------------------------------------------------------- sect array + companions
def test_sect_array_level_is_cached_and_expires(monkeypatch):
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                await bot.db.execute(
                    "INSERT INTO sects (name, patriarch_id, array_level) VALUES (?,?,?)",
                    ("Test Sect", 1, 3),
                )
                sect_id = 1

                await bot.sect_array_level(sect_id)      # warm the cache
                counts = {"fetch": 0}
                real_fetch = bot.db.fetchone

                async def spy_fetch(sql, params=()):
                    counts["fetch"] += 1
                    return await real_fetch(sql, params)

                monkeypatch.setattr(bot.db, "fetchone", spy_fetch)
                assert await bot.sect_array_level(sect_id) == 3   # cached
                assert counts["fetch"] == 0

                # Age past TTL -> refetch.
                entry = bot._sect_array_levels[sect_id]
                bot._sect_array_levels[sect_id] = (time.monotonic() - config.CACHE_TTL_SECONDS - 5, entry[1])
                assert await bot.sect_array_level(sect_id) == 3
                assert counts["fetch"] == 1
            finally:
                await bot.db.close()

    _run(main())


def test_sect_array_level_none_is_free():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                assert await bot.sect_array_level(None) == 0
                assert await bot.sect_array_level(0) == 0
            finally:
                await bot.db.close()

    _run(main())


def test_active_companions_is_cached(monkeypatch):
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                row, _ = await get_or_create_cultivator(bot.db, 777, "Companion Owner", 1)
                await bot.active_companions(row["id"])   # warm (1 fetchall)

                counts = {"fetchall": 0}
                real_fetchall = bot.db.fetchall

                async def spy_fetchall(sql, params=()):
                    counts["fetchall"] += 1
                    return await real_fetchall(sql, params)

                monkeypatch.setattr(bot.db, "fetchall", spy_fetchall)
                result = await bot.active_companions(row["id"])
                assert counts["fetchall"] == 0           # cached
                assert isinstance(result, list)
            finally:
                await bot.db.close()

    _run(main())


# ------------------------------------------------------ the hot path, end-to-end
def test_passive_qi_hot_path_drops_to_two_queries(monkeypatch):
    """A countable message with warm caches should do exactly ONE read (the
    cultivator row) + ONE write (the quota update) — down from ~5."""
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                user_id = 555
                row, _ = await get_or_create_cultivator(bot.db, user_id, "Riel", 1)
                # Warm every cache the hot path touches.
                await bot._guild_config(1)
                await bot.sect_array_level(row["sect_id"])   # NULL -> 0, no query
                await bot.active_companions(row["id"])       # 1 fetchall, warmed

                counts = {"fetch": 0, "fetchall": 0, "exec": 0}
                real_fetch, real_fetchall, real_exec = (
                    bot.db.fetchone, bot.db.fetchall, bot.db.execute,
                )

                async def spy_fetch(sql, params=()):
                    counts["fetch"] += 1
                    return await real_fetch(sql, params)

                async def spy_fetchall(sql, params=()):
                    counts["fetchall"] += 1
                    return await real_fetchall(sql, params)

                async def spy_exec(sql, params=()):
                    counts["exec"] += 1
                    return await real_exec(sql, params)

                monkeypatch.setattr(bot.db, "fetchone", spy_fetch)
                monkeypatch.setattr(bot.db, "fetchall", spy_fetchall)
                monkeypatch.setattr(bot.db, "execute", spy_exec)

                from cogs.passive_qi import PassiveQiCog

                cog = PassiveQiCog(bot)
                message = SimpleNamespace(
                    author=SimpleNamespace(
                        bot=False, id=user_id, display_name="Riel",
                    ),
                    guild=SimpleNamespace(id=1),
                    channel=SimpleNamespace(id=5),
                    content="Hello my fellow cultivators, the Dao calls!",
                )
                await cog.on_message(message)

                assert counts["fetch"] == 1        # cultivator row only
                assert counts["exec"] == 1         # quota update only
                assert counts["fetchall"] == 0     # companions were cached
            finally:
                await bot.db.close()

    _run(main())


def test_passive_qi_hot_path_with_sect_and_companions(monkeypatch):
    """Same path, but the cultivator HAS a sect (array level query warmed) so
    we prove the sect lookup is cached too, not just skipped."""
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = await _bot_with_db(Path(d))
            try:
                await bot.db.execute(
                    "INSERT INTO sects (name, patriarch_id, array_level) VALUES (?,?,?)",
                    ("Sword Pavilion", 1, 2),
                )
                row, _ = await get_or_create_cultivator(bot.db, 556, "Blade", 1)
                await bot.db.execute(
                    "UPDATE cultivators SET sect_id=1 WHERE id=?", (row["id"],),
                )
                row["sect_id"] = 1

                await bot._guild_config(1)
                await bot.sect_array_level(1)              # warm (fetchall-free)
                await bot.active_companions(row["id"])     # warm

                counts = {"fetch": 0, "exec": 0}
                real_fetch, real_exec = bot.db.fetchone, bot.db.execute

                async def spy_fetch(sql, params=()):
                    counts["fetch"] += 1
                    return await real_fetch(sql, params)

                async def spy_exec(sql, params=()):
                    counts["exec"] += 1
                    return await real_exec(sql, params)

                monkeypatch.setattr(bot.db, "fetchone", spy_fetch)
                monkeypatch.setattr(bot.db, "execute", spy_exec)

                from cogs.passive_qi import PassiveQiCog

                cog = PassiveQiCog(bot)
                message = SimpleNamespace(
                    author=SimpleNamespace(
                        bot=False, id=556, display_name="Blade",
                    ),
                    guild=SimpleNamespace(id=1),
                    channel=SimpleNamespace(id=5),
                    content="The sword remembers its first cut!",
                )
                await cog.on_message(message)

                assert counts["fetch"] == 1        # cultivator row only
                assert counts["exec"] == 1         # quota update only
            finally:
                await bot.db.close()

    _run(main())
