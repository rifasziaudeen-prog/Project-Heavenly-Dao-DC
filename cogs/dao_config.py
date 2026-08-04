"""Per-guild Dao configuration command (`/dao_config`, admin only)."""
from __future__ import annotations

import json

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import dao_bonds as bonds


class DaoConfigCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        if await self.bot.is_owner(interaction.user):
            return True
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
        cfg = await self.bot._guild_config(interaction.guild_id)
        if cfg["admin_user_id"] and interaction.user.id == cfg["admin_user_id"]:
            return True
        if cfg["admin_role_id"] and isinstance(interaction.user, discord.Member):
            return any(r.id == cfg["admin_role_id"] for r in interaction.user.roles)
        return False

    @app_commands.command(
        name="dao_config",
        description="Configure the Dao for this realm (admin only)",
    )
    @app_commands.choices(
        language=[
            app_commands.Choice(name="English (Pure English UI)", value="english"),
            app_commands.Choice(name="Bilingual (English + Chinese Flavor)", value="bilingual"),
        ]
    )
    async def dao_config(
        self,
        interaction: discord.Interaction,
        admin_role: discord.Role | None = None,
        admin_user: discord.User | None = None,
        erasure_enabled: bool | None = None,
        language: app_commands.Choice[str] | None = None,
        system_channel: discord.TextChannel | None = None,
        broadcast_channel: discord.TextChannel | None = None,
        add_disabled_channel: discord.TextChannel | None = None,
        remove_disabled_channel: discord.TextChannel | None = None,
        dao_male_role: discord.Role | None = None,
        dao_female_role: discord.Role | None = None,
    ) -> None:
        if not await self._is_admin(interaction):
            embed = discord.Embed(
                title="⛔ Mortal Presumption · 凡人之妄",
                description="Only the Heaven may command.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        updates: dict[str, object] = {"updated_at": ui.now_str()}
        notes: list[str] = []

        if admin_role is not None:
            updates["admin_role_id"] = admin_role.id
            notes.append(f"Admin role → <@&{admin_role.id}>")
        if admin_user is not None:
            updates["admin_user_id"] = admin_user.id
            notes.append(f"Admin user → <@{admin_user.id}>")
        if erasure_enabled is not None:
            updates["erasure_enabled"] = 1 if erasure_enabled else 0
            notes.append(f"Erasure → {'on · 开' if erasure_enabled else 'off · 关'}")
        if language is not None:
            updates["xianxia_terms_language"] = language.value
            notes.append(f"Language mode → **{language.name}**")
        if system_channel is not None:
            updates["system_channel_id"] = system_channel.id
            notes.append(f"System channel → {system_channel.mention}")
        if broadcast_channel is not None:
            updates["broadcast_channel_id"] = broadcast_channel.id
            notes.append(f"Broadcast channel → {broadcast_channel.mention}")

        if (
            dao_male_role is not None and dao_female_role is not None
            and dao_male_role.id == dao_female_role.id
        ):
            embed = discord.Embed(
                title="Role Conflict · 角色冲突",
                description=(
                    "The male and female gender roles must be two different roles."
                ),
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if dao_male_role is not None or dao_female_role is not None:
            role_map = bonds.parse_gender_map(cfg.get("dao_role_to_gender"))
            if dao_male_role is not None:
                role_map[str(dao_male_role.id)] = "male"
                notes.append(f"Male gender role → <@&{dao_male_role.id}>")
            if dao_female_role is not None:
                role_map[str(dao_female_role.id)] = "female"
                notes.append(f"Female gender role → <@&{dao_female_role.id}>")
            updates["dao_role_to_gender"] = json.dumps(role_map)

        if add_disabled_channel is not None or remove_disabled_channel is not None:
            disabled = ui.parse_json_list(cfg["qi_disabled_channels"])
            if add_disabled_channel is not None and add_disabled_channel.id not in disabled:
                disabled.append(add_disabled_channel.id)
                notes.append(f"Qi disabled channel + {add_disabled_channel.mention}")
            if remove_disabled_channel is not None and remove_disabled_channel.id in disabled:
                disabled.remove(remove_disabled_channel.id)
                notes.append(f"Qi disabled channel − {remove_disabled_channel.mention}")
            updates["qi_disabled_channels"] = str(disabled)

        if len(updates) == 1:  # only updated_at — nothing to change
            embed = discord.Embed(
                title="Dao Config · 天道律法",
                description=(
                    "No changes provided. Options: `admin_role`, `admin_user`, "
                    "`erasure_enabled`, `system_channel`, `broadcast_channel`, "
                    "`add_disabled_channel`, `remove_disabled_channel`, "
                    "`dao_male_role`, `dao_female_role`."
                ),
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        set_clause = ", ".join(f"{key}=?" for key in updates)
        await self.bot.db.execute(
            f"UPDATE guild_config SET {set_clause} WHERE guild_id=?",
            tuple(list(updates.values()) + [interaction.guild_id]),
        )

        embed = discord.Embed(
            title="☯ Dao Config Updated · 天道律法已改",
            description="\n".join(f"• {n}" for n in notes),
            color=ui.GOLD,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="setup_server",
        description="Auto-configure roles, categories, and channels for Heavenly Dao Engine (admin only)",
    )
    async def setup_server(self, interaction: discord.Interaction) -> None:
        if not await self._is_admin(interaction):
            embed = discord.Embed(
                title="⛔ Mortal Presumption · 凡人之妄",
                description="Only the Heaven may command.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Setup can take several seconds
        await interaction.response.defer(ephemeral=False)

        try:
            from scripts.setup_discord_server import ROLES_SPEC, STRUCTURE
        except ImportError:
            await interaction.followup.send("❌ Internal Error: Could not load setup script structures.")
            return

        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ This command must be run in a server.")
            return

        status_msg = await interaction.followup.send("⚡ Starting Xianxia Server Setup...")

        # ------------------------------------------------------------- 1. Roles
        created_roles = {}
        role_logs = []
        for rspec in ROLES_SPEC:
            existing = discord.utils.get(guild.roles, name=rspec["name"])
            if existing:
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
                role_logs.append(f"Created role: {rspec['name']}")
                created_roles[rspec["name"]] = new_role

        # --------------------------------------------------- 2. Categories & Channels
        announcements_channel = None
        rules_channel = None
        channel_logs = []

        for cat_spec in STRUCTURE:
            cat_name = cat_spec["category"]
            cat = discord.utils.get(guild.categories, name=cat_name)
            if not cat:
                cat = await guild.create_category(cat_name, reason="Heavenly Dao Setup")
                channel_logs.append(f"Created category: {cat_name}")

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
                    channel_logs.append(f"Created channel: #{ch_name}")
                else:
                    ch = existing_ch

                if ch_name == "announcements":
                    announcements_channel = ch
                elif ch_name == "rules-and-guide":
                    rules_channel = ch

        # ----------------------------------------------- 3. Welcome & Commands Guide
        guide_posted = False
        if rules_channel:
            # First check if guide is already posted
            async for msg in rules_channel.history(limit=10):
                if msg.author == self.bot.user and msg.embeds and "Welcome to the Heavenly Dao Engine Realm!" in msg.embeds[0].title:
                    guide_posted = True
                    break
            
            if not guide_posted:
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
                channel_logs.append("Posted Xianxia Welcome & Commands Guide.")

        # --------------------------------------------- 4. Update Database guild_config
        admin_role_id = created_roles["👑 Dao Ancestor"].id if "👑 Dao Ancestor" in created_roles else None
        announcement_channel_id = announcements_channel.id if announcements_channel else None

        gender_mapping = {}
        if "☯️ Yang Cultivator" in created_roles:
            gender_mapping[str(created_roles["☯️ Yang Cultivator"].id)] = "male"
        if "☯️ Yin Cultivator" in created_roles:
            gender_mapping[str(created_roles["☯️ Yin Cultivator"].id)] = "female"

        await self.bot.db.execute(
            "INSERT INTO guild_config (guild_id, xianxia_terms_language, admin_role_id, announcement_channel_id, dao_role_to_gender, erasure_enabled)"
            " VALUES (?, 'bilingual', ?, ?, ?, 1)"
            " ON CONFLICT(guild_id) DO UPDATE SET"
            " admin_role_id=excluded.admin_role_id,"
            " announcement_channel_id=excluded.announcement_channel_id,"
            " dao_role_to_gender=excluded.dao_role_to_gender",
            (guild.id, admin_role_id, announcement_channel_id, json.dumps(gender_mapping)),
        )

        # Build final summary
        summary = "🎉 DISCORD SERVER SETUP COMPLETE!"
        if not role_logs and not channel_logs:
            summary += "\n(All roles and channels were already correctly set up!)"
        else:
            if role_logs:
                summary += f"\n• Created {len(role_logs)} missing roles"
            if channel_logs:
                summary += f"\n• Created missing categories and channels"

        summary += "\n\nServer has been automatically configured with the Dao Ancestor admin role and gender tracking for Dao Bonds."

        await status_msg.edit(content=summary)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        content = message.content.strip().lower()

        # Text prefix fallback triggers for setup and command sync
        if content in ("!setup", "!setup_server", "!setup-server"):
            # Check admin permissions
            member = message.author if isinstance(message.author, discord.Member) else None
            is_owner = message.guild.owner_id == message.author.id or await self.bot.is_owner(message.author)
            is_admin = member.guild_permissions.administrator if member else False

            if not (is_owner or is_admin):
                await message.channel.send("⛔ **Mortal Presumption** · Only server administrators or the server owner may run setup.")
                return

            status_msg = await message.channel.send("⚡ **Starting Xianxia Server Setup...** Please wait...")

            try:
                from scripts.setup_discord_server import ROLES_SPEC, STRUCTURE
            except ImportError:
                await status_msg.edit(content="❌ Internal Error: Could not load setup script structures.")
                return

            guild = message.guild

            # 1. Roles
            created_roles = {}
            role_logs = []
            for rspec in ROLES_SPEC:
                existing = discord.utils.get(guild.roles, name=rspec["name"])
                if existing:
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
                    role_logs.append(f"Created role: {rspec['name']}")
                    created_roles[rspec["name"]] = new_role

            # 2. Categories & Channels
            announcements_channel = None
            rules_channel = None
            channel_logs = []

            for cat_spec in STRUCTURE:
                cat_name = cat_spec["category"]
                cat = discord.utils.get(guild.categories, name=cat_name)
                if not cat:
                    cat = await guild.create_category(cat_name, reason="Heavenly Dao Setup")
                    channel_logs.append(f"Created category: {cat_name}")

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
                        channel_logs.append(f"Created channel: #{ch_name}")
                    else:
                        ch = existing_ch

                    if ch_name == "announcements":
                        announcements_channel = ch
                    elif ch_name == "rules-and-guide":
                        rules_channel = ch

            # 3. Welcome & Commands Guide
            guide_posted = False
            if rules_channel:
                async for msg in rules_channel.history(limit=10):
                    if msg.author == self.bot.user and msg.embeds and "Welcome to the Heavenly Dao Engine Realm!" in msg.embeds[0].title:
                        guide_posted = True
                        break

                if not guide_posted:
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
                    channel_logs.append("Posted Xianxia Welcome & Commands Guide.")

            # 4. Database Config
            admin_role_id = created_roles["👑 Dao Ancestor"].id if "👑 Dao Ancestor" in created_roles else None
            announcement_channel_id = announcements_channel.id if announcements_channel else None

            gender_mapping = {}
            if "☯️ Yang Cultivator" in created_roles:
                gender_mapping[str(created_roles["☯️ Yang Cultivator"].id)] = "male"
            if "☯️ Yin Cultivator" in created_roles:
                gender_mapping[str(created_roles["☯️ Yin Cultivator"].id)] = "female"

            await self.bot.db.execute(
                "INSERT INTO guild_config (guild_id, xianxia_terms_language, admin_role_id, announcement_channel_id, dao_role_to_gender, erasure_enabled)"
                " VALUES (?, 'bilingual', ?, ?, ?, 1)"
                " ON CONFLICT(guild_id) DO UPDATE SET"
                " admin_role_id=excluded.admin_role_id,"
                " announcement_channel_id=excluded.announcement_channel_id,"
                " dao_role_to_gender=excluded.dao_role_to_gender",
                (guild.id, admin_role_id, announcement_channel_id, json.dumps(gender_mapping)),
            )

            # Sync slash commands immediately to this guild
            self.bot.tree.copy_global_to(guild=guild)
            await self.bot.tree.sync(guild=guild)

            summary = "🎉 **DISCORD SERVER SETUP COMPLETE!**"
            if not role_logs and not channel_logs:
                summary += "\n*(All roles and channels were already correctly set up!)*"
            else:
                if role_logs:
                    summary += f"\n• Created {len(role_logs)} missing roles"
                if channel_logs:
                    summary += f"\n• Created missing categories and channels"

            summary += "\n\nServer configuration and slash commands have been synced to this server!"
            await status_msg.edit(content=summary)

        elif content in ("!sync", "!sync_commands", "!sync-commands"):
            is_owner = message.guild.owner_id == message.author.id or await self.bot.is_owner(message.author)
            if not is_owner:
                return
            msg = await message.channel.send("🔄 **Syncing slash commands to this server...**")
            self.bot.tree.copy_global_to(guild=message.guild)
            await self.bot.tree.sync(guild=message.guild)
            await msg.edit(content="✅ **Slash commands synced to this server!** Type `/` to see all commands.")
