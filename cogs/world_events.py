"""World Events Cog — /events, /event_join, /event_attack, /event_status, /event_claim, and /spawn_event."""
from __future__ import annotations

import asyncio
import json
import random
import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import items as core_items, world_events as core_we
from db import queries


class WorldEventsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _cultivator(self, guild_id: int, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        return dict(row) if row else None

    # ================================================================= /events
    @app_commands.command(
        name="events",
        description="List active and upcoming world events",
    )
    async def events(self, interaction: discord.Interaction) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        evt_rows = await queries.active_or_upcoming_events(self.bot.db, interaction.guild_id)

        if not evt_rows:
            embed = discord.Embed(
                title=ui.format_title("No Active Calamities · 天灾未至", lang),
                description="The skies are peaceful. No world events scheduled at this moment.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=ui.format_title("🌌 World Events & Heavenly Calamities · 天降浩劫", lang),
            description="Unite with fellow cultivators to slay World Bosses for celestial rewards!",
            color=ui.GOLD,
        )

        for evt in evt_rows:
            hp_str = f"{evt['boss_hp_current']:,} / {evt['boss_hp_max']:,} HP"
            embed.add_field(
                name=f"Event #{evt['id']} — {evt['event_type'].replace('_', ' ').title()} ({evt['status'].upper()})",
                value=(
                    f"**Boss HP**: {hp_str} | **Phase**: {evt['current_phase']}/5\n"
                    f"**Scheduled**: {evt['scheduled_at']}\n"
                    f"*{evt['narrative_state']}*"
                ),
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================= /event_join
    @app_commands.command(
        name="event_join",
        description="Register your participation in a world event",
    )
    async def event_join(self, interaction: discord.Interaction, event_id: int) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        evt = await queries.event_by_id(self.bot.db, event_id)
        if not evt or evt["guild_id"] != interaction.guild_id:
            await interaction.response.send_message(f"Event #{event_id} not found.", ephemeral=True)
            return

        if evt["status"] not in ("pending", "active"):
            await interaction.response.send_message(f"Event #{event_id} is no longer accepting participants (Status: {evt['status']}).", ephemeral=True)
            return

        existing = await queries.event_participant(self.bot.db, event_id, row["id"])
        if existing:
            await interaction.response.send_message(f"You have already joined Event #{event_id}!", ephemeral=True)
            return

        await self.bot.db.execute(
            "INSERT INTO world_event_participants (event_id, cultivator_id, sect_id, damage_dealt)"
            " VALUES (?,?,?,0)",
            (event_id, row["id"], row["sect_id"]),
        )

        embed = discord.Embed(
            title=ui.format_title(f"⚔ Joined Calamity #{event_id} · 参战", lang),
            description=f"**{row['username']}** has joined the battle lines for **{evt['event_type'].replace('_', ' ').title()}**!\nPrepare your spiritual weapons with `/event_attack`!",
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # =========================================================== /event_attack
    @app_commands.command(
        name="event_attack",
        description="Attack the active World Boss in an event you joined",
    )
    async def event_attack(self, interaction: discord.Interaction, event_id: int) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        evt = await queries.event_by_id(self.bot.db, event_id)
        if not evt or evt["guild_id"] != interaction.guild_id:
            await interaction.response.send_message(f"Event #{event_id} not found.", ephemeral=True)
            return

        if evt["status"] != "active":
            await interaction.response.send_message(f"Event #{event_id} is not currently active (Status: {evt['status']}).", ephemeral=True)
            return

        part = await queries.event_participant(self.bot.db, event_id, row["id"])
        if not part:
            await interaction.response.send_message(f"Please `/event_join {event_id}` first before attacking!", ephemeral=True)
            return

        # Fetch equipped items
        eq_rows = await self.bot.db.fetchall("SELECT * FROM items WHERE owner_id=? AND is_equipped=1", (row["id"],))
        eq_bonuses = core_items.calculate_equipped_bonuses([dict(r) for r in eq_rows])

        stats = {
            "strength": row["strength"] + eq_bonuses["stat_buffs"]["physique"],
            "spirit": row["spirit"] + eq_bonuses["stat_buffs"]["spirit"],
        }
        weapon_bonus = sum(r.get("quantity", 1) * 20 for r in eq_rows if r.get("item_type") == "Weapon")
        sect_array_bonus = 1.0 + (await queries.sect_array_level(self.bot.db, row["sect_id"])) * 0.05

        damage = core_we.calculate_damage(
            stats,
            weapon_bonus=weapon_bonus,
            technique_mult=1.0 + (eq_bonuses["breakthrough_aid"] / 100.0),
            sect_array_bonus=sect_array_bonus,
            rng_factor=random.uniform(0.9, 1.1),
        )

        new_boss_hp = max(0, evt["boss_hp_current"] - damage)
        new_phase, phase_narrative = core_we.determine_boss_phase(new_boss_hp, evt["boss_hp_max"])
        new_status = "completed" if new_boss_hp <= 0 else "active"

        # Update participant damage
        await self.bot.db.execute(
            "UPDATE world_event_participants SET damage_dealt=damage_dealt+? WHERE event_id=? AND cultivator_id=?",
            (damage, event_id, row["id"]),
        )

        # Update event status & phase
        await self.bot.db.execute(
            "UPDATE world_events SET boss_hp_current=?, current_phase=?, narrative_state=?, status=? WHERE id=?",
            (new_boss_hp, new_phase, phase_narrative, new_status, event_id),
        )

        embed = discord.Embed(
            title=ui.format_title(f"💥 Strike Dealt: {damage:,} Damage! · 灵威重击", lang),
            description=(
                f"**{row['username']}** channels total focus into a devastating strike!\n"
                f"**Boss Remaining HP**: {new_boss_hp:,} / {evt['boss_hp_max']:,}\n"
                f"**Status**: *{phase_narrative}*"
            ),
            color=ui.GOLD if new_boss_hp > 0 else ui.PURPLE,
        )

        if new_boss_hp <= 0:
            embed.title = ui.format_title("🏆 WORLD BOSS SLAIN! · 天劫终结", lang)
            embed.description = f"**{row['username']}** delivered the final strike! The World Boss has been vanquished!\nUse `/event_claim {event_id}` to receive your ranking rewards."

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # =========================================================== /event_status
    @app_commands.command(
        name="event_status",
        description="Check boss HP, phase, and top damage leaderboard for an event",
    )
    async def event_status(self, interaction: discord.Interaction, event_id: int) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        evt = await queries.event_by_id(self.bot.db, event_id)
        if not evt or evt["guild_id"] != interaction.guild_id:
            await interaction.response.send_message(f"Event #{event_id} not found.", ephemeral=True)
            return

        parts = await queries.event_participants(self.bot.db, event_id)

        embed = discord.Embed(
            title=ui.format_title(f"📊 Event #{event_id} Status — {evt['event_type'].replace('_', ' ').title()}", lang),
            description=f"Status: **{evt['status'].upper()}** | Current Phase: **{evt['current_phase']}/5**",
            color=ui.CYAN,
        )

        embed.add_field(
            name="Boss HP Bar",
            value=f"{ui.progress_bar(evt['boss_hp_current'], evt['boss_hp_max'])}\n{evt['boss_hp_current']:,} / {evt['boss_hp_max']:,} HP",
            inline=False,
        )
        embed.add_field(name="Current Narrative State", value=f"*{evt['narrative_state']}*", inline=False)

        if parts:
            board_lines = []
            for i, p in enumerate(parts[:10], start=1):
                board_lines.append(f"**#{i} {p['username']}**: {p['damage_dealt']:,} damage")
            embed.add_field(name="Top Damage Leaderboard", value="\n".join(board_lines), inline=False)
        else:
            embed.add_field(name="Top Damage Leaderboard", value="No participants have attacked yet.", inline=False)

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================ /event_claim
    @app_commands.command(
        name="event_claim",
        description="Claim rewards for a completed world event",
    )
    async def event_claim(self, interaction: discord.Interaction, event_id: int) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        evt = await queries.event_by_id(self.bot.db, event_id)
        if not evt or evt["guild_id"] != interaction.guild_id:
            await interaction.response.send_message(f"Event #{event_id} not found.", ephemeral=True)
            return

        if evt["status"] != "completed":
            await interaction.response.send_message(f"Event #{event_id} has not concluded yet (Status: {evt['status']}).", ephemeral=True)
            return

        parts = await queries.event_participants(self.bot.db, event_id)
        rewards = core_we.calculate_event_rewards(parts)

        user_reward = next((r for r in rewards if r["cultivator_id"] == row["id"]), None)
        if not user_reward:
            await interaction.response.send_message("You did not participate in this event.", ephemeral=True)
            return

        part_row = await queries.event_participant(self.bot.db, event_id, row["id"])
        if part_row and part_row.get("reward_claimed"):
            await interaction.response.send_message("You have already claimed your rewards for this event!", ephemeral=True)
            return

        # Mark claimed
        await self.bot.db.execute(
            "UPDATE world_event_participants SET reward_claimed=1, final_rank=? WHERE event_id=? AND cultivator_id=?",
            (user_reward["rank"], event_id, row["id"]),
        )

        # Grant spirit stones & item reward
        await self.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?",
            (user_reward["spirit_stones"], row["id"]),
        )

        await core_items.grant_pill(
            self.bot.db, row["id"], user_reward["item_name"], user_reward["item_grade"],
            {"type": "stat_buff", "amount": 10}, quantity=1
        )

        if user_reward.get("title"):
            new_titles = ui.add_json_title(row["titles"], user_reward["title"])
            await self.bot.db.execute("UPDATE cultivators SET titles=? WHERE id=?", (new_titles, row["id"]))

        embed = discord.Embed(
            title=ui.format_title(f"🎁 Event #{event_id} Rewards Claimed! · 领赏", lang),
            description=(
                f"Your Final Rank: **#{user_reward['rank']}** ({part_row['damage_dealt']:,} Total Damage)\n\n"
                f"**Rewards Received:**\n"
                f"• 💎 **Spirit Stones**: +{user_reward['spirit_stones']:,}\n"
                f"• 📦 **Loot Item**: 1x {user_reward['item_name']} ({user_reward['item_grade']})\n"
                + (f"• 👑 **Exclusive Title**: `{user_reward['title']}`\n" if user_reward.get("title") else "")
            ),
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================ /spawn_event
    @app_commands.command(
        name="spawn_event",
        description="Admin command to schedule/spawn a new World Event",
    )
    @app_commands.choices(
        event_type=[
            app_commands.Choice(name="Demon Beast Siege", value="demon_beast_siege"),
            app_commands.Choice(name="Heavenly Tribulation Rain", value="heavenly_tribulation_rain"),
            app_commands.Choice(name="Ancient Ruin Awakening", value="ancient_ruin_awakening"),
            app_commands.Choice(name="Sect War", value="sect_war"),
            app_commands.Choice(name="Dao Competition", value="dao_competition"),
        ]
    )
    async def spawn_event(
        self,
        interaction: discord.Interaction,
        event_type: app_commands.Choice[str],
        boss_hp: int = 100000,
    ) -> None:
        if not await ui.is_admin(interaction, self.bot):
            await interaction.response.send_message("Only Dao Ancestors (Admins) may spawn World Events.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        cult_id = row["id"] if row else None

        cursor = await self.bot.db.execute(
            "INSERT INTO world_events (guild_id, event_type, scheduled_at, started_at, status, difficulty_rating, boss_hp_max, boss_hp_current, current_phase, narrative_state, created_by)"
            " VALUES (?,?,?,?,'active',1,?,?,1,'A cosmic aura descends as the World Boss awakens!',?)",
            (interaction.guild_id, event_type.value, ui.now_str(), ui.now_str(), boss_hp, boss_hp, cult_id),
        )

        event_id = cursor.lastrowid

        embed = discord.Embed(
            title=ui.format_title(f"⚡ WORLD EVENT SPAWNED! · Event #{event_id}", lang),
            description=(
                f"Admin **{interaction.user.display_name}** has summoned **{event_type.name}**!\n"
                f"Boss Max HP: **{boss_hp:,} HP**\n\n"
                f"Use `/event_join {event_id}` to enter the battlefield!"
            ),
            color=ui.CRIMSON,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)
