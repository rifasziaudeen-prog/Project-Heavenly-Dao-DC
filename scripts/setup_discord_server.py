#!/usr/bin/env python3
"""scripts/setup_discord_server.py

Automated Xianxia Discord Server Setup script for Heavenly Dao Engine.
Creates Categories, Channels, Roles, sets Permissions, posts a Welcome & Commands guide,
and configures guild_config in the database automatically.
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

from db.database import Database

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID_ENV = os.getenv("DEV_GUILD_ID")
DB_PATH = os.getenv("DATABASE_PATH", "heavenly_dao.db")

ROLES_SPEC = [
    {"name": "👑 Dao Ancestor", "color": discord.Color.gold(), "hoist": True, "admin": True},
    {"name": "☯️ Yang Cultivator", "color": discord.Color.blue(), "hoist": False, "admin": False},
    {"name": "☯️ Yin Cultivator", "color": discord.Color.magenta(), "hoist": False, "admin": False},
    {"name": "✨ Mortal Meridian", "color": discord.Color.light_grey(), "hoist": False, "admin": False},
    {"name": "🥉 Tier 1: Qi Condensation (练气)", "color": discord.Color.dark_teal(), "hoist": False, "admin": False},
    {"name": "🥈 Tier 2: Foundation Establishment (筑基)", "color": discord.Color.teal(), "hoist": False, "admin": False},
    {"name": "🥇 Tier 3: Golden Core (金丹)", "color": discord.Color.gold(), "hoist": False, "admin": False},
    {"name": "💎 Tier 4: Nascent Soul (元婴)", "color": discord.Color.purple(), "hoist": False, "admin": False},
    {"name": "🌌 Tier 5: Soul Formation (化神)", "color": discord.Color.dark_purple(), "hoist": False, "admin": False},
    {"name": "🔮 Tier 6: Void Refinement (炼虚)", "color": discord.Color.dark_magenta(), "hoist": False, "admin": False},
    {"name": "👑 Tier 7: Mahayana (大乘)", "color": discord.Color.dark_gold(), "hoist": False, "admin": False},
    {"name": "⚡ Tier 8: Tribulation Transcendance (渡劫)", "color": discord.Color.red(), "hoist": False, "admin": False},
    {"name": "☀️ Tier 9: Immortal Ascension (仙人)", "color": discord.Color.lighter_grey(), "hoist": True, "admin": False},
]

STRUCTURE = [
    {
        "category": "📜 ┊ HEAVENLY INFORMATION",
        "channels": [
            {"name": "announcements", "read_only": True, "topic": "Bot world events, server broadcasts, and Dao announcements"},
            {"name": "rules-and-guide", "read_only": True, "topic": "Game commands summary, server rules, and cultivation guide"},
        ],
    },
    {
        "category": "🌌 ┊ CULTIVATION GROUNDS",
        "channels": [
            {"name": "meditation-hall", "read_only": False, "topic": "Primary chat channel for cultivators to converse and passively accumulate Qi"},
            {"name": "breakthrough-tribulations", "read_only": False, "topic": "Dedicated channel for /cultivate and /breakthrough attempts"},
            {"name": "secret-realms", "read_only": False, "topic": "Channel for /realms, /enter_realm, /explore, and /retreat"},
            {"name": "dao-comprehension", "read_only": False, "topic": "Channel for /laws, /comprehend, and /law_status"},
        ],
    },
    {
        "category": "🏯 ┊ SECTS & BONDS",
        "channels": [
            {"name": "sect-hall", "read_only": False, "topic": "Channel for /sect_create, /sect_join, /sect_donate, /sect_upgrade"},
            {"name": "dao-bonds", "read_only": False, "topic": "Channel for /dao_bond, /dao_bond_accept, /dual_cultivate"},
        ],
    },
    {
        "category": "🏪 ┊ MARKETPLACE & ECONOMY",
        "channels": [
            {"name": "heavenly-market", "read_only": False, "topic": "Channel for /market, /sell, /buy, /bid, /my_listings, /trade"},
            {"name": "alchemy-pavilion", "read_only": False, "topic": "Channel for /recipes, /alchemy_status, /refine_pill"},
        ],
    },
    {
        "category": "⚡ ┊ CALAMITIES & EVENTS",
        "channels": [
            {"name": "world-boss-battlefield", "read_only": False, "topic": "Channel for /events, /event_join, /event_attack, /event_status, /event_claim"},
        ],
    },
]


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

        print(f"⚡ Starting Xianxia Server Setup for Guild: '{guild.name}' (ID: {guild.id})...")

        # ------------------------------------------------------------- 1. Roles
        created_roles = {}
        for rspec in ROLES_SPEC:
            existing = discord.utils.get(guild.roles, name=rspec["name"])
            if existing:
                print(f"  -> Role '{rspec['name']}' already exists.")
                created_roles[rspec["name"]] = existing
            else:
                perms = discord.Permissions.all() if rspec["admin"] else discord.Permissions.general()
                new_role = await guild.create_role(
                    name=rspec["name"],
                    color=rspec["color"],
                    hoist=rspec["hoist"],
                    permissions=perms,
                    reason="Heavenly Dao Engine Automated Setup",
                )
                print(f"  -> Created Role: '{rspec['name']}'")
                created_roles[rspec["name"]] = new_role

        # --------------------------------------------------- 2. Categories & Channels
        announcements_channel = None
        rules_channel = None

        for cat_spec in STRUCTURE:
            cat_name = cat_spec["category"]
            cat = discord.utils.get(guild.categories, name=cat_name)
            if not cat:
                cat = await guild.create_category(cat_name, reason="Heavenly Dao Setup")
                print(f"  -> Created Category: '{cat_name}'")

            for ch_spec in cat_spec["channels"]:
                ch_name = ch_spec["name"]
                existing_ch = discord.utils.get(cat.text_channels, name=ch_name)
                if not existing_ch:
                    overwrites = {}
                    if ch_spec["read_only"]:
                        overwrites[guild.default_role] = discord.PermissionOverwrite(send_messages=False, read_messages=True)
                        if "👑 Dao Ancestor" in created_roles:
                            overwrites[created_roles["👑 Dao Ancestor"]] = discord.PermissionOverwrite(send_messages=True)

                    ch = await cat.create_text_channel(
                        name=ch_name,
                        topic=ch_spec["topic"],
                        overwrites=overwrites,
                        reason="Heavenly Dao Setup",
                    )
                    print(f"     -> Created Channel: #{ch_name}")
                else:
                    ch = existing_ch
                    print(f"     -> Channel #{ch_name} already exists.")

                if ch_name == "announcements":
                    announcements_channel = ch
                elif ch_name == "rules-and-guide":
                    rules_channel = ch

        # ----------------------------------------------- 3. Welcome & Commands Guide
        if rules_channel:
            embed = discord.Embed(
                title="🌌 Welcome to the Heavenly Dao Engine Realm! · 天道纪元",
                description=(
                    "Embark on your journey from a mortal with clogged meridians to an immortal deity who commands the cosmic laws!\n\n"
                    "**Getting Started:**\n"
                    "1. Use `/register` to create your cultivator persona and reveal your **Spiritual Aptitude Profile**.\n"
                    "2. Chat in `#meditation-hall` to passively absorb Qi into your dantian.\n"
                    "3. Run `/cultivate` and `/breakthrough` in `#breakthrough-tribulations` to ascend realms!\n\n"
                    "**Core Commands Guide:**\n"
                    "• `/profile` — View your realm, Qi, stats, title, and physique\n"
                    "• `/aptitudes` — View your Five Phases (五行), Martial Intents & Yin-Yang balance\n"
                    "• `/inventory` & `/equip` — Equip weapons, scrolls, and pills\n"
                    "• `/refine_pill` — Craft celestial pills in the 3-stage alchemy mini-game\n"
                    "• `/realms` & `/explore` — Explore secret realm dungeon instances\n"
                    "• `/events` & `/event_attack` — Join server-wide World Boss battles\n"
                    "• `/laws` & `/comprehend` — Master the 5 Fundamental Laws of Existence\n"
                    "• `/market` & `/sell` — Trade items for spirit stones in the Auction House\n"
                    "• `/sect_create` & `/sect_join` — Form sects and build ancient arrays\n"
                    "• `/help` — Full categorised command reference guide"
                ),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="Heavenly Dao Engine v1.1.0 · 天道引擎")
            await rules_channel.send(embed=embed)
            print("  -> Posted Xianxia Welcome & Commands Guide to #rules-and-guide.")

        # --------------------------------------------- 4. Update Database guild_config
        db = Database(Path(DB_PATH))
        await db.connect()

        admin_role_id = created_roles["👑 Dao Ancestor"].id if "👑 Dao Ancestor" in created_roles else None
        announcement_channel_id = announcements_channel.id if announcements_channel else None

        gender_mapping = {}
        if "☯️ Yang Cultivator" in created_roles:
            gender_mapping[str(created_roles["☯️ Yang Cultivator"].id)] = "male"
        if "☯️ Yin Cultivator" in created_roles:
            gender_mapping[str(created_roles["☯️ Yin Cultivator"].id)] = "female"

        await db.execute(
            "INSERT INTO guild_config (guild_id, xianxia_terms_language, admin_role_id, announcement_channel_id, dao_role_to_gender, erasure_enabled)"
            " VALUES (?, 'bilingual', ?, ?, ?, 1)"
            " ON CONFLICT(guild_id) DO UPDATE SET"
            " admin_role_id=excluded.admin_role_id,"
            " announcement_channel_id=excluded.announcement_channel_id,"
            " dao_role_to_gender=excluded.dao_role_to_gender",
            (guild.id, admin_role_id, announcement_channel_id, json.dumps(gender_mapping)),
        )
        await db.close()

        print(f"\n🎉 DISCORD SERVER SETUP COMPLETE FOR '{guild.name}'!")
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

    target_guild_id = int(guild_id_str)
    client = ServerSetupClient(target_guild_id)
    asyncio.run(client.start(TOKEN))


if __name__ == "__main__":
    main()
