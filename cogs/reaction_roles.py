"""Self-serve reaction roles for the role-selection channel.

Members tap a reaction on the role-selection board (posted by the server
setup) to claim their gender, martial path, element root, and culture role.
Picking a role automatically removes the others in its exclusive group (one
gender, one path, one root). The emoji→role map lives in
``core.server_layout.REACTION_ROLE_MAP`` so setup and this cog can never drift.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from core.server_layout import (
    REACTION_ROLE_MAP,
    ROLE_SELECTION_CHANNEL,
    resolve_reaction_add,
    resolve_reaction_remove,
)

log = logging.getLogger("heavenly_dao")


def _normalize_emoji(emoji) -> str:
    """Strip variation selectors so '🗡️' and '🗡' compare equal."""
    return str(emoji).replace("\ufe0f", "")


class ReactionRolesCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self._handle(payload, added=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        await self._handle(payload, added=False)

    async def _handle(self, payload: discord.RawReactionActionEvent, added: bool) -> None:
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return
        emoji_key = _normalize_emoji(payload.emoji)
        if emoji_key not in REACTION_ROLE_MAP:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = guild.get_channel(payload.channel_id)
        if channel is None or getattr(channel, "name", "") != ROLE_SELECTION_CHANNEL:
            return

        # Only react to the bot's own role-selection board message.
        try:
            msg = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return
        if msg.author.id != self.bot.user.id:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException:
                return

        role_name = REACTION_ROLE_MAP[emoji_key]
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            log.warning("Reaction role %r not found in guild %s", role_name, guild.name)
            return

        current = {r.name for r in member.roles}
        try:
            if added:
                to_add, to_remove = resolve_reaction_add(current, emoji_key)
                for name in to_add:
                    target = discord.utils.get(guild.roles, name=name)
                    if target is not None and name not in current:
                        await member.add_roles(target, reason="Reaction role: role-selection board")
                for name in to_remove:
                    target = discord.utils.get(guild.roles, name=name)
                    if target is not None:
                        await member.remove_roles(target, reason="Reaction role: exclusive group swap")
            else:
                for name in resolve_reaction_remove(current, emoji_key):
                    target = discord.utils.get(guild.roles, name=name)
                    if target is not None:
                        await member.remove_roles(target, reason="Reaction role: unreacted")
        except discord.HTTPException:
            log.exception("Failed to update reaction roles for user %s", payload.user_id)
