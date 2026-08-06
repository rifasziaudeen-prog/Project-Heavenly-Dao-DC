"""Reincarnation Cog — /reincarnate, /past_lives, and /legacy commands."""
from __future__ import annotations

import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import reincarnation as core_reinc
from db import queries


class ConfirmRebirthView(discord.ui.View):
    def __init__(self, user_id: int, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This rebirth threshold belongs to another soul!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm Rebirth · 确认轮回", style=discord.ButtonStyle.danger, custom_id="btn_confirm_rebirth")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel · 取消", style=discord.ButtonStyle.secondary, custom_id="btn_cancel_rebirth")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = False
        await interaction.response.send_message("You step back from the threshold of Samsara.", ephemeral=True)
        self.stop()


class ReincarnationCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _cultivator(self, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
        )
        return dict(row) if row else None

    # ========================================================== /reincarnate
    @app_commands.command(
        name="reincarnate",
        description="Trigger voluntary rebirth (Requires Nascent Soul / Tier 5+ with half-full dantian)",
    )
    async def reincarnate(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        can_reinc, err_msg = core_reinc.can_voluntary_reincarnate(row)
        if not can_reinc:
            embed = discord.Embed(
                title=ui.format_title("Rebirth Gate Sealed · 轮回未开启", lang),
                description=err_msg,
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        inv_rows = await self.bot.db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND quantity > 0",
            (row["id"],),
        )
        inventory = [dict(r) for r in inv_rows]

        legacy = core_reinc.calculate_legacy(row, inventory)
        retained = legacy["retained_stats"]
        cycle = legacy["cycle_bonus"]
        next_cycle = row.get("reincarnation_cycle", 0) + 1
        new_physique = core_reinc.get_physique_name(next_cycle)

        tech_str = retained["technique"] or "None"

        embed = discord.Embed(
            title=ui.format_title(f"🌀 Threshold of Rebirth — Cycle {row.get('reincarnation_cycle', 0)} → {next_cycle}", lang),
            description=(
                f"You stand at the threshold of Samsara. Rebirth will reset your realm to **Mortal (Tier 1)**, "
                f"deduct all Qi, and clear inventory gear (protection charms are kept).\n\n"
                f"**Retained Legacy:**\n"
                f"• 🧠 **Comprehension Retention**: +{retained['comprehension']} ({cycle['comprehension_bonus']} cycle bonus)\n"
                f"• 🍀 **Luck Retention**: +{retained['luck']}\n"
                f"• 📜 **Retained Technique**: {tech_str}\n"
                f"• ⚡ **Breakthrough Success Bonus**: +{cycle['breakthrough_bonus']:.0%}\n"
                f"• 🧬 **New Physique**: {new_physique}\n\n"
                f"**Epitaph:**\n*{legacy['epitaph']}*"
            ),
            color=ui.PURPLE,
        )
        embed.set_footer(text="Are you certain you wish to shed your mortal vessel and be reborn?")

        view = ConfirmRebirthView(user_id=interaction.user.id, timeout=30.0)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        await view.wait()
        if not view.confirmed:
            return

        # Execute the Rebirth as a single transaction: the cultivator reset,
        # the inventory wipe, and the log entry all commit together — or a
        # crash mid-sequence leaves the player exactly as they were.
        updates, log_entry = core_reinc.execute_rebirth_payload(row, inventory, reason="voluntary")

        async with self.bot.db.transaction():
            # 1. Update cultivator
            set_clauses = ", ".join(f"{k}=?" for k in updates.keys())
            params = list(updates.values()) + [row["id"]]
            await self.bot.db.execute(f"UPDATE cultivators SET {set_clauses} WHERE id=?", params)

            # 2. Clear non-talisman/non-charm items from inventory
            await self.bot.db.execute(
                "DELETE FROM items WHERE owner_id=? AND item_type != 'Talisman'",
                (row["id"],),
            )

            # 3. Log reincarnation
            await self.bot.db.execute(
                "INSERT INTO reincarnation_log (cultivator_id, cycle_from, cycle_to, reason, realm_tier_at_death, realm_sub_stage_at_death, comprehension_retained, luck_retained, technique_retained, epitaph)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    log_entry["cultivator_id"],
                    log_entry["cycle_from"],
                    log_entry["cycle_to"],
                    log_entry["reason"],
                    log_entry["realm_tier_at_death"],
                    log_entry["realm_sub_stage_at_death"],
                    log_entry["comprehension_retained"],
                    log_entry["luck_retained"],
                    log_entry["technique_retained"],
                    log_entry["epitaph"],
                ),
            )

        pub_embed = discord.Embed(
            title=ui.format_title(f"⚡ {row['username']} Has Chosen Rebirth! · 舍身入轮回", lang),
            description=(
                f"The old vessel shatters into starlight! A new cultivator awakens with **{new_physique}**!\n\n"
                f"🌀 **Cycle {next_cycle} Begins.** May the Heavenly Dao guide your path."
            ),
            color=ui.GOLD,
        )
        pub_embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.channel.send(embed=pub_embed)

    # ========================================================== /past_lives
    @app_commands.command(
        name="past_lives",
        description="View your reincarnation history log, epitaphs, and unlocked past life memories",
    )
    async def past_lives(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        history = await queries.reincarnation_history(self.bot.db, row["id"])

        embed = discord.Embed(
            title=ui.format_title(f"📜 {row['username']}'s Samsara Register · 轮回图录", lang),
            description=f"Reincarnation Cycle: **{row['reincarnation_cycle']}** | Physique: **{row['cultivation_physique']}**",
            color=ui.PURPLE,
        )

        # Check memory unlocks
        memories = []
        comp = row["comprehension"]
        if comp >= 100 and row["reincarnation_cycle"] > 0:
            memories.append("• 🔮 *Whispers from a past life echo in your mind...*")
        if comp >= 250 and row["reincarnation_cycle"] > 0:
            memories.append("• 🔮 *A flash of memory: your previous death. You shudder.*")
        if comp >= 500 and row["reincarnation_cycle"] > 0:
            tech = row.get("inherited_technique") or "Ancient Scripture"
            memories.append(f"• 🔮 *You recall the origin of '{tech}' from your past life.*")
        if comp >= 1000 and row["reincarnation_cycle"] > 0:
            memories.append(f"• 🔮 *Ultimate Truth: You have returned {row['reincarnation_cycle']} times. The Dao fears you.*")

        if memories:
            embed.add_field(name="Past Life Memories", value="\n".join(memories), inline=False)

        if history:
            log_lines = []
            for h in history[:5]:
                tech = h["technique_retained"] or "None"
                log_lines.append(
                    f"**Cycle {h['cycle_from']} → {h['cycle_to']}** ({h['reason'].title()})\n"
                    f"Ended at Tier {h['realm_tier_at_death']} | Retained: Comp +{h['comprehension_retained']}, Luck +{h['luck_retained']}, Tech: {tech}\n"
                    f"📜 *\"{h['epitaph']}\"*"
                )
            embed.add_field(name="Past Life Logs", value="\n\n".join(log_lines), inline=False)
        else:
            embed.add_field(name="Past Life Logs", value="This is your first lifetime. No past reincarnation records found.", inline=False)

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================== /legacy
    @app_commands.command(
        name="legacy",
        description="Preview what stats, bonuses, and techniques you would retain upon reincarnation",
    )
    async def legacy(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        inv_rows = await self.bot.db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND quantity > 0",
            (row["id"],),
        )
        inventory = [dict(r) for r in inv_rows]

        legacy_data = core_reinc.calculate_legacy(row, inventory)
        retained = legacy_data["retained_stats"]
        cycle = legacy_data["cycle_bonus"]
        next_cycle = row.get("reincarnation_cycle", 0) + 1

        embed = discord.Embed(
            title=ui.format_title(f"✨ Legacy Preview · 宿世传承 (Cycle {row['reincarnation_cycle']} → {next_cycle})", lang),
            description="Preview of stats and advantages you would carry forward into your next life:",
            color=ui.CYAN,
        )
        embed.add_field(name="Comprehension Retained", value=f"+{retained['comprehension']} (+{cycle['comprehension_bonus']} cycle bonus)", inline=True)
        embed.add_field(name="Luck Retained", value=f"+{retained['luck']}", inline=True)
        embed.add_field(name="Unspent Points Retained", value=f"{retained['stat_points']} points (50%)", inline=True)
        embed.add_field(name="Retained Technique", value=retained["technique"] or "None", inline=True)
        embed.add_field(name="Breakthrough Success Bonus", value=f"+{cycle['breakthrough_bonus']:.0%}", inline=True)
        embed.add_field(name="Next Physique", value=core_reinc.get_physique_name(next_cycle), inline=True)
        embed.add_field(name="Current Epitaph", value=f"*{legacy_data['epitaph']}*", inline=False)

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)
