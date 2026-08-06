"""Passive Qi listener — turns chat activity into cultivation power.

Rules (user spec):
  * every countable message awards tiny Qi (~10% of a /cultivate)
  * cap: 15 counted messages / player / hour
  * anti-spam: <5 chars ignored; identical message within 60s ignored
  * channel blacklist (spam channels) / whitelist from per-guild config
  * gains are memory-buffered and flushed in batches (qi_flush_loop)
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from bot import utils as ui
from config import default as config
from core import math as gm, passive_logic
from db.queries import get_or_create_cultivator

log = logging.getLogger("heavenly_dao")


class PassiveQiCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if message.content.startswith("/"):
            return
        if not passive_logic.is_countable_message(
            message.content, config.MESSAGE_MIN_LENGTH
        ):
            return

        key = (message.guild.id, message.author.id)
        last = self.bot._last_msg.get(key)
        last_content, last_ts = last if last else (None, None)
        if passive_logic.is_repeat(
            message.content, last_content, last_ts, time.time(),
            config.MESSAGE_REPEAT_WINDOW_SECONDS,
        ):
            return
        # Record BEFORE any await so interleaved messages from the same author
        # cannot both pass the repeat guard (single-threaded asyncio ordering).
        self.bot._last_msg[key] = (message.content, time.time())

        cfg = await self.bot._guild_config(message.guild.id)
        disabled = ui.parse_json_list(cfg["qi_disabled_channels"])
        if message.channel.id in disabled:
            return
        enabled = ui.parse_json_list(cfg["qi_enabled_channels"])
        if enabled and message.channel.id not in enabled:
            return

        row, _ = await get_or_create_cultivator(
            self.bot.db, message.author.id, message.author.display_name,
            message.guild.id,
        )
        now = time.time()
        allowed, count, window_start = passive_logic.consume_message_quota(
            row["message_qi_count"], row["message_qi_window_start"], now,
            config.MESSAGE_QI_HOURLY_CAP,
        )
        if not allowed:
            await self._track_denial(message, window_start)
            return

        # Persist the quota count IMMEDIATELY — before the awaits below — so a
        # second concurrent message from the same author sees the updated count
        # (prevents exceeding the hourly cap under interleaved handlers).
        await self.bot.db.execute(
            "UPDATE cultivators SET message_qi_count=?, message_qi_window_start=?"
            " WHERE id=?",
            (count, window_start, row["id"]),
        )
        gain = gm.calculate_qi_gain(
            row["realm_tier"], row["comprehension"], source="message",
            sect_array_level=await self.bot.sect_array_level(row["sect_id"]),
            has_sect=bool(row["sect_id"]),
            active_companions=await self.bot.active_companions(row["id"]),
        )
        self.bot.qi_buffer.append({
            "cid": row["id"], "guild_id": message.guild.id, "qi": gain, "source": "message",
        })
        if len(self.bot.qi_buffer) >= config.QI_BUFFER_MAX_ROWS:
            await self.bot.flush_qi_buffer()

    async def _track_denial(self, message: discord.Message, window_start: str) -> None:
        key = (message.guild.id, message.author.id)
        denials, window = self.bot._deny_counts.get(key, (0, window_start))
        if window != window_start:
            denials = 0
        denials += 1
        self.bot._deny_counts[key] = (denials, window_start)
        if denials >= config.FLAG_DENY_THRESHOLD:
            await self.bot.add_flag(
                message.guild.id, message.author.id, "qi_rate_abuse",
                "Exceeded the hourly message Qi cap repeatedly",
            )
            self.bot._deny_counts[key] = (0, window_start)
