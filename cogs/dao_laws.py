"""Dao Laws Cog — /laws, /comprehend, and /law_status commands.

Thin glue only: all rank / insight / resistance rules live in core/dao_laws.py,
so future balance changes touch one file.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import dao_laws as core_dl
from core import items as core_items
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
            description=(
                "Comprehend fundamental laws of reality to unlock celestial power and "
                "prepare for Dao Fusion. Each law has **5 Ranks** (20/40/60/80/100)."
            ),
            color=ui.PURPLE,
        )

        for law in laws_all:
            pl = player_law_map.get(law["id"])
            mastery = pl["mastery_percentage"] if pl else 0.0
            insights = pl["insights_gained"] if pl else 0

            rank_label = core_dl.law_rank_label(mastery)
            needed, at = core_dl.next_rank_progress(mastery)
            resist = core_dl.law_resistance(mastery)
            bar = ui.progress_bar(int(mastery), 100)
            req_str = f"Tier {law['realm_required']} | Comp {law['comprehension_required']}"

            next_line = "👑 Max Rank" if needed == 0 else f"Next: Rank {core_dl.law_rank(mastery) + 1} at {at}% ({needed} pts)"
            embed.add_field(
                name=f"{law['name']} ({law['name_zh']}) — {rank_label}",
                value=(
                    f"{bar}\n"
                    f"**Mastery**: {mastery:.1f}% · **Resistance**: {resist:.0%} vs {law['name_zh']} attacks\n"
                    f"**{next_line}**\n"
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

        # Deterministic insight gain: 2 + 悟性//100 (aptitude = learning speed)
        gain = core_dl.calculate_insight_gain(row["comprehension"], "comprehend")
        new_mastery = min(100.0, prev_mastery + gain)
        rank_ups = core_dl.check_rank_ups(new_mastery, prev_mastery)

        # Deduct Qi
        await self.bot.db.execute(
            "UPDATE cultivators SET qi_current=qi_current-100 WHERE id=?",
            (row["id"],),
        )

        if pl:
            await self.bot.db.execute(
                "UPDATE cultivator_laws SET mastery_percentage=?, insights_gained=insights_gained+1,"
                " last_enlightenment_at=? WHERE cultivator_id=? AND law_id=?",
                (new_mastery, ui.now_str(), row["id"], law["id"]),
            )
        else:
            await self.bot.db.execute(
                "INSERT INTO cultivator_laws (cultivator_id, law_id, mastery_percentage,"
                " insights_gained, last_enlightenment_at) VALUES (?,?,?,1,?)",
                (row["id"], law["id"], new_mastery, ui.now_str()),
            )

        rank_label = core_dl.law_rank_label(new_mastery)
        embed = discord.Embed(
            title=ui.format_title(f"✨ Epiphany: {law['name']} ({law['name_zh']})", lang),
            description=(
                f"You close your eyes and channel your consciousness into the cosmic fabric...\n"
                f"**Insight Gained**: **+{gain:.0f}** mastery points (悟性 {row['comprehension']})\n"
                f"**Current Mastery**: **{new_mastery:.1f}%** — {rank_label}\n\n"
                f"*{law['law_lore']}*"
            ),
            color=ui.GOLD,
        )

        if rank_ups:
            labels = [f"**{core_dl.LAW_RANKS[r - 1][0]}** ({core_dl.LAW_RANKS[r - 1][1]})" for r in rank_ups]
            embed.add_field(
                name="🎉 RANK UP!",
                value=f"Your comprehension of {law['name_zh']} has reached {' and '.join(labels)}! New passive law bonuses unlocked.",
                inline=False,
            )

        if core_dl.law_rank(new_mastery) >= 5:
            embed.add_field(
                name="👑 DAO FUSION GATEWAY UNLOCKED!",
                value="You have achieved **Rank 5 — Transcendence (超脱)** in this law! You meet the prerequisite for **Dao Fusion Ascension (Tier 8→9)**!",
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================== /law_status
    @app_commands.command(
        name="law_status",
        description="View lore, rank ladder, and milestone effects for a specified fundamental law",
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
        embed.add_field(name="Comprehension Required", value=str(law["comprehension_required"]), inline=True)

        # Rank ladder with per-rank resistance
        ladder_lines = []
        for i, (en, cn) in enumerate(core_dl.LAW_RANKS, start=1):
            threshold = core_dl.LAW_RANK_THRESHOLDS[i - 1]
            resist = i * core_dl.LAW_RESISTANCE_PER_RANK
            ladder_lines.append(
                f"• **Rank {i}** ({threshold}%) — {en} {cn} · **{resist:.0%} resistance**"
            )
        embed.add_field(name="Rank Ladder · 境界阶梯", value="\n".join(ladder_lines), inline=False)

        if effects:
            effect_lines = []
            for threshold, eff in sorted(effects.items(), key=lambda x: int(x[0])):
                effect_lines.append(f"• **Rank {core_dl.law_rank(float(threshold))}** ({threshold}%): {eff}")
            embed.add_field(name="Rank Effects", value="\n".join(effect_lines), inline=False)

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)
