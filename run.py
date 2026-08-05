"""Heavenly Dao Engine — entry point.

Usage:
    python run.py
"""
import asyncio

from config import default as config
from bot.main import HeavenlyDaoBot


async def main() -> None:
    if not config.DISCORD_TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and add your bot token."
        )
    bot = HeavenlyDaoBot()
    try:
        await bot.start(config.DISCORD_TOKEN, reconnect=True)
    finally:
        # Graceful shutdown: closing the bot also closes the SQLite connection,
        # which releases aiosqlite's worker thread and checkpoints the WAL.
        # Without this, Ctrl+C left the process alive forever, holding
        # heavenly_dao.db locked so the bot could not be restarted.
        try:
            await bot.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
