"""Dao Laws Cog — /laws, /comprehend, and /law_status commands."""
from __future__ import annotations

import asyncio
import json
import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import dao_laws as core_dl
from db import queries


class DaoLawsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _cultivator(self, guild_id: int, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        return dict(row) if row else None

    # =================================================================== /laws
    @app_commands.command(
        name="laws",
        description="View your mastery over the Fundamental Laws of Existence",
    )
    async def laws(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        laws_all = await queries.dao_laws_all(self.bot.db)
        player_laws = await queries.cultivator_laws_all(self.bot.db, row["id"])
        player_law_map = {pl["law_id"]: pl for pl in player_laws}

        embed = discord.Embed(
            title=ui.format_title(f"🌌 {row['username']}'s Dao Laws Register · 法则图录", lang),
            description="Comprehend fundamental laws of reality to unlock celestial power and prepare for Dao Fusion.",
            color=ui.PURPLE,
        )

        for law in laws_all:
            pl = player_law_map.get(law["id"])
            mastery = pl["mastery_percentage"] if pl else 0.0
            insights = pl["insights_gained"] if pl else 0

            # Progress bar
            bar = ui.progress_bar(int(mastery), 100)
            req_str = f"Tier {law['realm_required']} | Comp {law['comprehension_required']}"

            embed.add_field(
                name=f"{law['name']} ({law['name_zh']}) — {mastery:.1f}% Mastery",
                value=(
                    f"{bar}\n"
                    f"**Requirements**: {req_str}\n"
                    f"**Insights Meditated**: {insights} times"
                ),
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================== /comprehend
    @app_commands.command(
        name="comprehend",
        description="Meditate on a fundamental law to gain insight (Requires Nascent Soul / Tier 5+)",
    )
    async def comprehend(self, interaction: discord.Interaction, law_name: str) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        law = await queries.dao_law_by_name(self.bot.db, law_name)
        if not law:
            await interaction.response.send_message(f"Law **{law_name}** not found. Check `/laws` for catalog.", ephemeral=True)
            return

        can_access, err_msg = core_dl.can_comprehend_law(row, law)
        if not can_access:
            embed = discord.Embed(
                title=ui.format_title("Comprehension Sealed · 无法感悟", lang),
                description=err_msg,
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check 100 Qi cost
        if row["qi_current"] < 100:
            await interaction.response.send_message("Meditating on a Dao Law requires **100 Qi**. Consume pills or `/cultivate` to replenish.", ephemeral=True)
            return

        # Fetch existing record
        pl = await queries.cultivator_law(self.bot.db, row["id"], law["id"])
        prev_mastery = pl["mastery_percentage"] if pl else 0.0

        # Calculate insight gain
        gain = core_dl.calculate_insight_gain("comprehend")
        new_mastery = min(100.0, prev_mastery + gain)
        crossed_milestones = core_dl.check_milestones(new_mastery, prev_mastery)

        # Deduct Qi
        await self.bot.db.execute(
            "UPDATE cultivators SET qi_current=qi_current-100 WHERE id=?",
            (row["id"],),
        )

        if pl:
            m25 = pl["milestone_25_reached"] or (25 in crossed_milestones)
            m50 = pl["milestone_50_reached"] or (50 in crossed_milestones)
            m75 = pl["milestone_75_reached"] or (75 in crossed_milestones)
            m100 = pl["milestone_100_reached"] or (100 in crossed_milestones)

            await self.bot.db.execute(
                "UPDATE cultivator_laws SET mastery_percentage=?, insights_gained=insights_gained+1, milestone_25_reached=?, milestone_50_reached=?, milestone_75_reached=?, milestone_100_reached=?, last_enlightenment_at=? WHERE cultivator_id=? AND law_id=?",
                (new_mastery, m25, m50, m75, m100, ui.now_str(), row["id"], law["id"]),
            )
        else:
            m25 = 25 in crossed_milestones
            m50 = 50 in crossed_milestones
            m75 = 75 in crossed_milestones
            m100 = 100 in crossed_milestones

            await self.bot.db.execute(
                "INSERT INTO cultivator_laws (cultivator_id, law_id, mastery_percentage, insights_gained, milestone_25_reached, milestone_50_reached, milestone_75_reached, milestone_100_reached, last_enlightenment_at)"
                " VALUES (?,?,?,1,?,?,?,?,?)",
                (row["id"], law["id"], new_mastery, m25, m50, m75, m100, ui.now_str()),
            )

        embed = discord.Embed(
            title=ui.format_title(f"✨ Epiphany: {law['name']} ({law['name_zh']})", lang),
            description=(
                f"You close your eyes and channel your consciousness into the cosmic fabric...\n"
                f"**Insight Gained**: +{gain:.2f}% Mastery!\n"
                f"**Current Mastery**: **{new_mastery:.2f}%** / 100.0%\n\n"
                f"*{law['law_lore']}*"
            ),
            color=ui.GOLD,
        )

        if crossed_milestones:
            m_str = ", ".join(f"**{m}%**" for m in crossed_milestones)
            embed.add_field(
                name="🎉 MILESTONE ACHIEVED!",
                value=f"Crossed {m_str} Mastery threshold! New passive law bonuses unlocked.",
                inline=False,
            )

        if 100 in crossed_milestones:
            embed.add_field(
                name="👑 DAO FUSION GATEWAY UNLOCKED!",
                value="You have achieved **100% Complete Law Mastery**! You meet the prerequisite for **Dao Fusion Ascension (Tier 7→8)**!",
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================== /law_status
    @app_commands.command(
        name="law_status",
        description="View lore and milestone effects for a specified fundamental law",
    )
    async def law_status(self, interaction: discord.Interaction, law_name: str) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        law = await queries.dao_law_by_name(self.bot.db, law_name)
        if not law:
            await interaction.response.send_message(f"Law **{law_name}** not found.", ephemeral=True)
            return

        effects = core_items.parse_effect_data(law["mastery_effect"]) or {}

        embed = discord.Embed(
            title=ui.format_title(f"📜 {law['name']} ({law['name_zh']}) · 法则密卷", lang),
            description=f"*{law['law_lore']}*",
            color=ui.PURPLE,
        )
        embed.add_field(name="Min Realm Required", value=f"Tier {law['realm_required']}", inline=True)
        embed.add_field(name="Comprehension Required", value=str(law['comprehension_required']), inline=True)

        if effects:
            effect_lines = []
            for threshold, eff in sorted(effects.items(), key=lambda x: int(x[0])):
                effect_lines.append(f"• **{threshold}% Milestone**: {eff}")
            embed.add_field(name="Milestone Effects", value="\n".join(effect_lines), inline=False)

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)
