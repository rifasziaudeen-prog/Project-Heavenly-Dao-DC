#!/usr/bin/env python3
"""scripts/setup_discord_server.py

Automated Xianxia Discord Server Setup for Heavenly Dao Engine.

Builds the FULL v2 blueprint (see ``core.server_layout``): 27 roles with real
permissions, 8 themed categories, ~34 channels (text + voice) with per-role
permission overwrites, a rich welcome experience, and a reaction-role channel.

The blueprint lives in ONE place — ``core/server_layout.py`` — and is shared by:
  * this standalone script,
  * the in-Discord ``/setup_server`` slash command,
  * the ``!setup`` text fallback (both in ``cogs/dao_config.py``).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import discord
from dotenv import load_dotenv

# Ensure root directory in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.server_layout import (  # noqa: E402
    ANNOUNCEMENTS_CHANNEL,
    COMMAND_REFERENCE_CHANNEL,
    GETTING_STARTED_CHANNEL,
    REACTION_ROLE_MAP,
    ROLE_SELECTION_CHANNEL,
    ROLES_SPEC,
    RULES_CHANNEL,
    STRUCTURE,
    WELCOME_CHANNEL,
    channel_overwrites,
    resolve_color,
    role_permissions,
)
from db.database import Database  # noqa: E402

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID_ENV = os.getenv("DEV_GUILD_ID")
DB_PATH = os.getenv("DATABASE_PATH", "heavenly_dao.db")

# Re-exported for backward compatibility (cogs may import these names).
__all__ = ["ROLES_SPEC", "STRUCTURE", "apply_server_setup"]

REASON = "Heavenly Dao Engine Automated Setup"


# --------------------------------------------------------------------------- builders
async def ensure_roles(guild: discord.Guild) -> tuple[dict[str, discord.Role], list[str]]:
    """Get-or-create every role in ROLES_SPEC. Returns (name→role, created names)."""
    roles: dict[str, discord.Role] = {}
    created: list[str] = []
    for rspec in ROLES_SPEC:
        existing = discord.utils.get(guild.roles, name=rspec["name"])
        if existing:
            roles[rspec["name"]] = existing
        else:
            new_role = await guild.create_role(
                name=rspec["name"],
                color=resolve_color(rspec["color"]),
                hoist=rspec.get("hoist", False),
                mentionable=rspec.get("mentionable", False),
                permissions=role_permissions(rspec),
                reason=REASON,
            )
            roles[rspec["name"]] = new_role
            created.append(rspec["name"])
    return roles, created


async def ensure_structure(
    guild: discord.Guild, roles: dict[str, discord.Role]
) -> tuple[dict[str, discord.abc.GuildChannel], list[str]]:
    """Get-or-create every category and channel. Returns (slug→channel, log lines)."""
    channels: dict[str, discord.abc.GuildChannel] = {}
    logs: list[str] = []
    for cat_spec in STRUCTURE:
        cat_name = cat_spec["category"]
        cat = discord.utils.get(guild.categories, name=cat_name)
        if not cat:
            cat = await guild.create_category(cat_name, reason=REASON)
            logs.append(f"Created category: {cat_name}")

        for ch_spec in cat_spec["channels"]:
            ch_name = ch_spec["name"]
            kind = ch_spec.get("kind", "text")
            # Look up server-wide first: Discord enforces unique channel names
            # across the whole guild, so a same-named channel in another
            # category (or a stray user channel) must be reused, not re-created.
            existing = discord.utils.get(guild.channels, name=ch_name)
            if existing is None:
                overwrites = channel_overwrites(ch_spec, roles, guild.default_role)
                if kind == "voice":
                    # NOTE: create_voice_channel accepts no topic kwarg.
                    existing = await cat.create_voice_channel(
                        name=ch_name, overwrites=overwrites, reason=REASON,
                    )
                    logs.append(f"Created voice channel: {ch_name}")
                else:
                    existing = await cat.create_text_channel(
                        name=ch_name, topic=ch_spec["topic"],
                        overwrites=overwrites, reason=REASON,
                    )
                    logs.append(f"Created channel: #{ch_name}")
            channels[ch_name] = existing
    return channels, logs


async def _find_guide(channel: discord.TextChannel, marker: str):
    """Find the existing guide message (pinned first, then recent history)."""
    try:
        for msg in await channel.pins():
            if msg.author == channel.guild.me and msg.embeds and marker in (msg.embeds[0].title or ""):
                return msg
    except discord.HTTPException:
        pass
    try:
        async for msg in channel.history(limit=100):
            if msg.author == channel.guild.me and msg.embeds and marker in (msg.embeds[0].title or ""):
                return msg
    except discord.HTTPException:
        pass
    return None


async def _post_if_absent(
    channel: discord.TextChannel, embed: discord.Embed, marker: str, pin: bool = False
) -> bool:
    """Send ``embed`` unless a message with ``marker`` in its title already exists."""
    if await _find_guide(channel, marker) is not None:
        return False
    try:
        sent = await channel.send(embed=embed)
    except discord.HTTPException:
        return False
    if pin:
        try:
            await sent.pin(reason=REASON)
        except discord.HTTPException:
            pass
    return True


async def post_welcome_content(
    guild: discord.Guild, channels: dict[str, discord.abc.GuildChannel], roles: dict[str, discord.Role]
) -> list[str]:
    """Post the welcome embeds + role-selection message (idempotent). Returns log lines."""
    logs: list[str] = []
    gold = discord.Color.gold()

    # 1. Welcome
    welcome = channels.get(WELCOME_CHANNEL)
    if isinstance(welcome, discord.TextChannel):
        embed = discord.Embed(
            title="🌌 Welcome to the Heavenly Dao · 天道纪元",
            description=(
                "You stand at the foot of the mountain, a mortal with clogged meridians.\n"
                "Here, even the lowliest stone may ascend to become a star. ✨\n\n"
                "**Your first three steps:**\n"
                "1. **`/register`** — awaken your cultivation and reveal your Spiritual Root\n"
                "2. **`/cultivate`** — absorb 灵力 and grow your dantian\n"
                "3. **`/breakthrough`** — face the tribulation and ascend realms\n\n"
                "Choose your gender, martial path, and element root in "
                f"<#{channels[ROLE_SELECTION_CHANNEL].id}> if it exists!"
                if ROLE_SELECTION_CHANNEL in channels else
                "Choose your path in the role-selection channel below. 🎭"
            ),
            color=gold,
        )
        embed.add_field(name="📜 Rules", value=f"See <#{channels[RULES_CHANNEL].id}>" if RULES_CHANNEL in channels else "See #rules-and-guide", inline=True)
        embed.add_field(name="🌱 Getting Started", value=f"See <#{channels[GETTING_STARTED_CHANNEL].id}>" if GETTING_STARTED_CHANNEL in channels else "See #getting-started", inline=True)
        embed.set_footer(text="Heavenly Dao Engine · 天道引擎")
        if await _post_if_absent(welcome, embed, "Welcome to the Heavenly Dao"):
            logs.append("Posted welcome guide to #welcome")

    # 2. Rules & command guide
    rules = channels.get(RULES_CHANNEL)
    if isinstance(rules, discord.TextChannel):
        embed = discord.Embed(
            title="📜 Rules & Command Guide · 门规与功法",
            description=(
                "**The Three Rules of the Realm:**\n"
                "1. **Respect all cultivators** — no harassment, hate, or doxxing. ⛩️\n"
                "2. **No cheating the Dao** — anti-cheat is watching; bans are permanent. 🚫\n"
                "3. **Keep the world alive** — roleplay lightly, chat freely, be kind. 💫\n\n"
                "**Quick start:** `/register` → `/cultivate` → `/breakthrough`\n"
                "Type `/help` for the full categorized command reference, or read "
                f"<#{channels[COMMAND_REFERENCE_CHANNEL].id}>."
                if COMMAND_REFERENCE_CHANNEL in channels else
                "**Quick start:** `/register` → `/cultivate` → `/breakthrough`\n"
                "Type `/help` for the full categorized command reference."
            ),
            color=gold,
        )
        embed.set_footer(text="Heavenly Dao Engine · 天道引擎")
        if await _post_if_absent(rules, embed, "Rules & Command Guide", pin=True):
            logs.append("Posted rules & command guide to #rules-and-guide")

    # 3. Getting started
    start = channels.get(GETTING_STARTED_CHANNEL)
    if isinstance(start, discord.TextChannel):
        embed = discord.Embed(
            title="🌱 The Path to Immortality · 成仙之路",
            description=(
                "**Chapter 1 — Awakening:** `/register` reveals your Five Phases (五行), "
                "Martial Intents, and Yin-Yang balance. Chat in `#meditation-hall` to "
                "passively absorb Qi (up to 15 messages/hour).\n\n"
                "**Chapter 2 — Foundation:** fill your dantian with `/cultivate`, then "
                "face `/breakthrough` tribulations in `#breakthrough-tribulations` to "
                "rise through the nine realms.\n\n"
                "**Chapter 3 — Wealth:** `/refine_pill` in `#alchemy-pavilion`, trade in "
                "`#heavenly-market`, form sects in `#sect-hall`, and bond with a "
                "dao companion in `#dao-bonds`.\n\n"
                "**Chapter 4 — Glory:** join World Boss battles in "
                "`#world-boss-battlefield`, master the Laws in `#dao-comprehension`, "
                "and carve your name onto the leaderboards."
            ),
            color=discord.Color.teal(),
        )
        embed.set_footer(text="Heavenly Dao Engine · 天道引擎")
        if await _post_if_absent(start, embed, "Path to Immortality", pin=True):
            logs.append("Posted getting-started guide to #getting-started")

    # 4. Command reference
    reference = channels.get(COMMAND_REFERENCE_CHANNEL)
    if isinstance(reference, discord.TextChannel):
        embed = discord.Embed(
            title="📚 Command Reference · 功法总纲",
            description=(
                "**Identity & Progress:** `/register` `/profile` `/aptitudes` `/breakthrough` `/inventory` `/equip`\n"
                "**Cultivation:** `/cultivate` `/passive_qi` `/meridians` `/titles`\n"
                "**Realms & Laws:** `/realms` `/enter_realm` `/explore` `/retreat` `/laws` `/comprehend` `/law_status`\n"
                "**Alchemy & Items:** `/recipes` `/refine_pill` `/alchemy_status` `/use` `/forge`\n"
                "**Economy:** `/market` `/sell` `/buy` `/bid` `/my_listings` `/cancel_listing` `/trade` `/trade_accept` `/trade_decline`\n"
                "**Sects & Bonds:** `/sect_create` `/sect_join` `/sect_donate` `/sect_upgrade` `/dao_bond` `/dao_bond_accept` `/dual_cultivate`\n"
                "**Events:** `/events` `/event_join` `/event_attack` `/event_status` `/event_claim`\n"
                "**Server:** `/help` `/profile [member]` — and admins: `/heaven_panel` `/setup_server` `/dao_config`"
            ),
            color=discord.Color.dark_teal(),
        )
        embed.set_footer(text="Type /help for details on any command · 天道引擎")
        if await _post_if_absent(reference, embed, "Command Reference"):
            logs.append("Posted command reference to #command-reference")

    # 5. Reaction-role selection
    selection = channels.get(ROLE_SELECTION_CHANNEL)
    if isinstance(selection, discord.TextChannel):
        embed = discord.Embed(
            title="🎭 Choose Your Dao Path · 道途抉择",
            description=(
                "React below to claim your identity — picking a new one automatically "
                "swaps the old. 🌟\n\n"
                "**☯️ Gender:** 🌞 Yang (male) · 🌙 Yin (female)\n"
                "**⚔️ Martial Path:** 🗡️ Sword Saint · ⚔️ Sabre Lord · 🏹 Spear Master · 👊 Fist Tyrant\n"
                "**🌱 Element Root:** 🔥 Fire · 💧 Water · 🌿 Wood · 🪨 Earth · ⚙️ Metal · 🌪️ Qi\n"
                "**📖 Culture:** 📜 Dao Scholar · 🎨 Spirit Painter"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Tap a reaction to toggle your role · 天道引擎")
        posted = await _post_if_absent(selection, embed, "Choose Your Dao Path", pin=True)
        if posted:
            logs.append("Posted role-selection board to #role-selection")
        # Attach any MISSING reactions to the board (new or pre-existing), so a
        # re-run repairs a board that lost reactions to a partial failure.
        board = await _find_guide(selection, "Choose Your Dao Path")
        if board is not None:
            present = {str(r.emoji).replace("\ufe0f", "") for r in board.reactions}
            for emoji in REACTION_ROLE_MAP:
                if emoji in present:
                    continue
                try:
                    await board.add_reaction(emoji)
                except discord.HTTPException:
                    pass
    return logs


async def apply_server_setup(
    guild: discord.Guild,
) -> dict:
    """Create roles, channels, and welcome content for ``guild``.

    Returns a summary dict: {"roles", "channels", "role_logs", "channel_logs",
    "content_logs"} — every entry point (script, slash command, !setup) uses
    this one function, so behavior can never drift between them.
    """
    roles, role_logs = await ensure_roles(guild)
    channels, channel_logs = await ensure_structure(guild, roles)
    content_logs = await post_welcome_content(guild, channels, roles)
    return {
        "roles": roles,
        "channels": channels,
        "role_logs": role_logs,
        "channel_logs": channel_logs,
        "content_logs": content_logs,
    }


# --------------------------------------------------------------------------- standalone client
class ServerSetupClient(discord.Client):
    def __init__(self, target_guild_id: int):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        super().__init__(intents=intents)
        self.target_guild_id = target_guild_id

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            print(f"❌ Guild ID {self.target_guild_id} not found! Check DEV_GUILD_ID in .env.")
            await self.close()
            return

        print(f"⚡ Building the Heavenly Dao realm for '{guild.name}' (ID: {guild.id})...")
        try:
            result = await apply_server_setup(guild)
        except Exception as exc:
            print(f"❌ Setup failed: {exc}")
            await self.close()
            return
        roles, channels = result["roles"], result["channels"]

        for name in result["role_logs"]:
            print(f"  -> Created role: {name}")
        for line in result["channel_logs"]:
            print(f"  -> {line}")
        for line in result["content_logs"]:
            print(f"  -> {line}")

        # Persist guild_config (admin role, announcement channel, gender mapping).
        db = Database(Path(DB_PATH))
        await db.connect()
        admin_role = roles.get("👑 Dao Ancestor")
        ann_channel = channels.get(ANNOUNCEMENTS_CHANNEL)
        gender_mapping = {}
        if "☯️ Yang Cultivator" in roles:
            gender_mapping[str(roles["☯️ Yang Cultivator"].id)] = "male"
        if "☯️ Yin Cultivator" in roles:
            gender_mapping[str(roles["☯️ Yin Cultivator"].id)] = "female"
        await db.execute(
            "INSERT INTO guild_config (guild_id, xianxia_terms_language, admin_role_id, announcement_channel_id, dao_role_to_gender, erasure_enabled)"
            " VALUES (?, 'bilingual', ?, ?, ?, 1)"
            " ON CONFLICT(guild_id) DO UPDATE SET"
            " admin_role_id=excluded.admin_role_id,"
            " announcement_channel_id=excluded.announcement_channel_id,"
            " dao_role_to_gender=excluded.dao_role_to_gender",
            (guild.id, admin_role.id if admin_role else None,
             ann_channel.id if ann_channel else None, json.dumps(gender_mapping)),
        )
        await db.close()

        print(f"\n🎉 THE HEAVENLY DAO REALM IS BUILT FOR '{guild.name}'!")
        print(f"   {len(roles)} roles · {len(channels)} channels · {len(result['content_logs'])} guide messages posted")
        await self.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        print("Usage: python scripts/setup_discord_server.py [guild_id]")
        print("Set DISCORD_TOKEN and DEV_GUILD_ID in .env or pass target guild ID as argument.")
        sys.exit(0)

    if not TOKEN:
        print("❌ DISCORD_TOKEN is missing in .env file.")
        sys.exit(1)

    guild_id_str = GUILD_ID_ENV
    if len(sys.argv) > 1:
        guild_id_str = sys.argv[1]

    if not guild_id_str:
        print("❌ Please specify target Guild ID in .env (DEV_GUILD_ID=...) or as command argument.")
        sys.exit(1)

    client = ServerSetupClient(int(guild_id_str))
    asyncio.run(client.start(TOKEN))


if __name__ == "__main__":
    main()
