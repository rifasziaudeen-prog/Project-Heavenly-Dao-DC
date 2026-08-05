"""Transcendence — the voluntary endgame prestige loop.

At the summit of the Dao (Beyond Dao 超脱, 9th Layer) a cultivator may shed
their vessel and begin again. Transcendence is NOT death: it resets active
attributes (realm, Qi, Heart Demon) while permanently stacking generous gifts
(+15 all stats, +5,000 Qi capacity, a Transcendent title, and one cycling
permanent passive). Everything is deterministic (core/math.py) — no LLM, no RNG.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import math as gm
from db.queries import get_or_create_cultivator


class _TranscendView(discord.ui.View):
    """Confirm / decline buttons for a transcendence (author-only)."""

    def __init__(self, bot, author_id: int, cultivator_id: int, payload: dict,
                 title: str, passive_desc: str) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.cultivator_id = cultivator_id
        self.payload = payload
        self.title = title
        self.passive_desc = passive_desc
        self.applied = False

    async def _disable(self, interaction: discord.Interaction, content: str) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="⬆️ Transcend Now · 超脱", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the cultivator who stands at the summit may transcend.",
                ephemeral=True,
            )
            return
        if self.applied:
            await interaction.response.send_message(
                "This transcendence is already being processed.", ephemeral=True
            )
            return
        self.applied = True

        try:
            set_clause = ", ".join(f"{k}=?" for k in self.payload)
            await self.bot.db.execute(
                f"UPDATE cultivators SET {set_clause} WHERE id=?",
                tuple(list(self.payload.values()) + [self.cultivator_id]),
            )
        except Exception:
            self.applied = False
            await interaction.response.edit_message(
                content="The heavens faltered — your transcendence was not consumed. Try again.",
                view=self,
            )
            return
        await self._disable(interaction, content=None)

        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE id=?", (self.cultivator_id,)
        )
        embed = discord.Embed(
            title=f"☯ Transcendence Complete · {self.title}",
            description=(
                f"{interaction.user.mention} shattered the heavens and returned to the "
                f"**{ui.realm_summary(row['realm_tier'], row['realm_sub_stage'])}** — "
                f"reborn, but forever **more**.\n\n"
                f"**Permanent gifts accumulated (cycle {row['transcendence_count']}):**"
            ),
            color=ui.GOLD,
        )
        embed.add_field(
            name="Core Stats",
            value=(f"Strength {row['strength']} · Spirit {row['spirit']} · Physique {row['physique']}\n"
                   f"Luck {row['luck']} · Comprehension {row['comprehension']}"),
            inline=True,
        )
        embed.add_field(
            name="Vessel",
            value=f"Qi capacity **{ui.format_qi(row['qi_capacity'])}**\n+{row['transcendence_qi_gain_bonus']} flat Qi per /cultivate",
            inline=True,
        )
        embed.add_field(
            name="New Passive",
            value=self.passive_desc,
            inline=False,
        )
        embed.set_footer(text=f"Transcendence {row['transcendence_count']} · 超脱次数")
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Never Mind · 再思", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the cultivator may answer for their Dao.",
                ephemeral=True,
            )
            return
        if self.applied:
            return
        self.applied = True
        await self._disable(interaction, content="The Dao waits for another lifetime. · 大道未弃")


class TranscendenceCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ============================================================== /transcend
    @app_commands.command(
        name="transcend",
        description="At the summit (Beyond Dao, 9th layer): shed your vessel for permanent gifts",
    )
    async def transcend(self, interaction: discord.Interaction) -> None:
        row, _ = await get_or_create_cultivator(
            self.bot.db, interaction.guild_id, interaction.user.id,
            interaction.user.display_name,
        )
        if row["realm_tier"] < gm.TRANSCENDENCE_REALM or row["realm_sub_stage"] < gm.TRANSCENDENCE_LAYER:
            embed = discord.Embed(
                title="The Summit Awaits · 超脱之门未开",
                description=(
                    f"Only a cultivator at the **summit of the Dao** — "
                    f"**{gm.realm_name(gm.TRANSCENDENCE_REALM)} 超脱, 9th Layer** — may "
                    f"transcend. You stand at the "
                    f"**{ui.realm_summary(row['realm_tier'], row['realm_sub_stage'])}**.\n\n"
                    "Continue cultivating. The heavens are patient."
                ),
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        payload = gm.transcendence_payload(dict(row))
        next_count = int(row["transcendence_count"]) + 1
        title = gm.transcendence_title(next_count)
        passive = gm.next_legacy_passive(next_count)
        # Record the title in both the active slot and the permanent titles list.
        payload["title"] = title
        payload["titles"] = ui.add_json_title(row["titles"], title)

        embed = discord.Embed(
            title="☯ The Door of Transcendence · 超脱之门",
            description=(
                f"{interaction.user.mention}, you have reached **Beyond Dao 超脱 (9th Layer)** — "
                "the end of the known ladder. Beyond it lies **transcendence**: shed this vessel, "
                "return to Mortal, and carry **permanent gifts** into every lifetime after.\n\n"
                f"**Cycle {next_count} will grant forever:**\n"
                f"• **+15** to all five core stats\n"
                f"• **+5,000** Qi capacity (survives every breakthrough)\n"
                f"• **+100** flat Qi per /cultivate\n"
                f"• Title **{title}**\n"
                f"• Permanent passive: **{passive['name']}** — {passive['desc']}\n\n"
                "Your realm, Qi, and Heart Demon reset to a fresh start. "
                "Your items, sect, bonds, karma, aptitudes, and Dao Laws remain."
            ),
            color=ui.GOLD,
        )
        view = _TranscendView(
            self.bot, interaction.user.id, row["id"],
            payload, title, f"**{passive['name']}** — {passive['desc']}",
        )
        await interaction.response.send_message(embed=embed, view=view)
