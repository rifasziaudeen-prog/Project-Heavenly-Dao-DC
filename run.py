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
    await bot.start(config.DISCORD_TOKEN, reconnect=True)


if __name__ == "__main__":
    asyncio.run(main())
