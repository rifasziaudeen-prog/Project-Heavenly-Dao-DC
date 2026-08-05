"""Sects — player-run organizations with array bonuses and a spirit-stone economy.

A sect grants its members a Qi-accumulation array bonus (powered by treasury
donations and upgraded by the patriarch). All validation and math is
deterministic (`core/sects.py`) — no LLM, no RNG.
"""
from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import sects
from db.queries import (
    get_or_create_cultivator,
    sect_by_name,
    sect_member_count,
    sect_members,
)


class SectsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------- helpers
    async def _cultivator(self, user_id: int):
        return await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
        )

    async def _sect_of(self, cultivator_row) -> dict | None:
        if not cultivator_row or not cultivator_row["sect_id"]:
            return None
        row = await self.bot.db.fetchone(
            "SELECT * FROM sects WHERE id=?", (cultivator_row["sect_id"],)
        )
        return dict(row) if row else None

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

    async def _patriarch_row(self, sect: dict):
        """Fetch the patriarch cultivator row for a sect."""
        if not sect.get("patriarch_id"):
            return None
        return await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE id=?", (sect["patriarch_id"],)
        )

    @staticmethod
    def _refuse(interaction: discord.Interaction, reason: str):
        return interaction.response.send_message(
            embed=discord.Embed(
                title="⛔ Forbidden · 天道不许",
                description=reason,
                color=ui.CRIMSON,
            ),
            ephemeral=True,
        )

    # ============================================================== /sect create
    @app_commands.command(
        name="sect_create",
        description="Found a new sect and become its Patriarch",
    )
    async def sect_create(
        self, interaction: discord.Interaction, name: str
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me:
            await self._refuse(interaction, "You must `/register` before founding a sect.")
            return

        ok, reason = sects.validate_sect_creation(name, me["realm_tier"])
        if not ok:
            await self._refuse(interaction, reason)
            return

        if me["sect_id"]:
            await self._refuse(
                interaction,
                "You already belong to a sect. `/sect leave` before founding your own.",
            )
            return

        existing = await sect_by_name(self.bot.db, name)
        if existing:
            await self._refuse(
                interaction,
                f"A sect named **{name}** already exists. Choose another name.",
            )
            return

        cursor = await self.bot.db.execute(
            "INSERT INTO sects (name, patriarch_id, alignment)"
            " VALUES (?,?,?)",
            (name, me["id"], "Neutral"),
        )
        sect_id = cursor.lastrowid
        await self.bot.db.execute(
            "UPDATE cultivators SET sect_id=?, sect_rank=? WHERE id=?",
            (sect_id, "Patriarch", me["id"]),
        )

        embed = discord.Embed(
            title="🏯 Sect Founded · 立宗",
            description=(
                f"{interaction.user.mention} has founded **{name}**.\n"
                "The Heaven recognizes a new lineage."
            ),
            color=ui.GOLD,
        )
        embed.add_field(name="Patriarch · 掌门", value=interaction.user.mention, inline=True)
        embed.add_field(name="Array Level · 阵法", value="1 (+8% Qi)", inline=True)
        embed.add_field(
            name="Recruit",
            value=f"`/sect join {name}` to join this lineage.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    # ============================================================== /sect join
    @app_commands.command(
        name="sect_join",
        description="Join an existing sect as an Outer Disciple",
    )
    async def sect_join(
        self, interaction: discord.Interaction, name: str
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me:
            await self._refuse(interaction, "You must `/register` before joining a sect.")
            return

        sect = await sect_by_name(self.bot.db, name)
        if not sect:
            await self._refuse(interaction, f"No sect named **{name}** exists.")
            return

        count = await sect_member_count(self.bot.db, sect["id"])
        ok, reason = sects.validate_join(
            has_sect=bool(me["sect_id"]),
            max_members=sect["max_members"],
            current_count=count,
        )
        if not ok:
            await self._refuse(interaction, reason)
            return

        await self.bot.db.execute(
            "UPDATE cultivators SET sect_id=?, sect_rank=? WHERE id=?",
            (sect["id"], "Outer Disciple", me["id"]),
        )

        embed = discord.Embed(
            title="🤝 Sect Joined · 入宗",
            description=(
                f"{interaction.user.mention} has joined **{sect['name']}** as an "
                f"**{sects.SECT_RANK_LABELS['Outer Disciple']}**."
            ),
            color=ui.GOLD,
        )
        embed.add_field(
            name="Array Bonus · 阵法加成",
            value=f"+{sects.array_bonus_pct(sect['array_level']):.0f}% Qi",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    # ============================================================== /sect leave
    @app_commands.command(
        name="sect_leave",
        description="Leave your current sect (a Patriarch leaving disbands it)",
    )
    async def sect_leave(self, interaction: discord.Interaction) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me or not me["sect_id"]:
            await self._refuse(interaction, "You do not belong to a sect.")
            return

        sect = await self._sect_of(me)
        is_patriarch = sect and sect["patriarch_id"] == me["id"]

        if is_patriarch:
            # Disband: clear all members, delete the sect row.
            await self.bot.db.execute(
                "UPDATE cultivators SET sect_id=NULL, sect_rank='Outer Disciple'"
                " WHERE sect_id=?",
                (sect["id"],),
            )
            await self.bot.db.execute("DELETE FROM sects WHERE id=?", (sect["id"],))
            embed = discord.Embed(
                title="🏚 Sect Disbanded · 散宗",
                description=(
                    f"{interaction.user.mention} has disbanded **{sect['name']}**.\n"
                    "All members are now sectless. The lineage fades into legend."
                ),
                color=ui.CRIMSON,
            )
        else:
            await self.bot.db.execute(
                "UPDATE cultivators SET sect_id=NULL, sect_rank='Outer Disciple'"
                " WHERE id=?",
                (me["id"],),
            )
            embed = discord.Embed(
                title="👋 Sect Left · 离宗",
                description=(
                    f"{interaction.user.mention} has left **{sect['name']}**."
                ),
                color=ui.CYAN,
            )
        await interaction.response.send_message(embed=embed)

    # ============================================================== /sect info
    @app_commands.command(
        name="sect_info",
        description="View a sect's dashboard (members, array, treasury)",
    )
    async def sect_info(
        self, interaction: discord.Interaction, name: str | None = None
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        sect = None
        if name:
            sect = await sect_by_name(self.bot.db, name)
        elif me and me["sect_id"]:
            sect = await self._sect_of(me)

        if not sect:
            hint = "Use `/sect_info <name>` to inspect a sect." if name else (
                "You belong to no sect. Use `/sect_info <name>`."
            )
            await self._refuse(interaction, f"No sect found. {hint}")
            return

        members = await sect_members(self.bot.db, sect["id"])
        patriarch = await self._patriarch_row(sect)

        embed = discord.Embed(
            title=f"🏯 {sect['name']} · 宗门",
            description=f"Alignment: **{sect['alignment']}**",
            color=ui.GOLD,
        )
        embed.add_field(
            name="Patriarch · 掌门",
            value=f"<@{patriarch['user_id']}>" if patriarch else "Unknown",
            inline=True,
        )
        embed.add_field(
            name="Members · 弟子",
            value=f"{len(members)} / {sect['max_members']}",
            inline=True,
        )
        embed.add_field(
            name="Array · 阵法",
            value=f"Level {sect['array_level']} (+{sects.array_bonus_pct(sect['array_level']):.0f}% Qi)",
            inline=True,
        )
        embed.add_field(
            name="Treasury · 灵石库",
            value=f"{sect['treasury_stones']:,} 💎",
            inline=True,
        )
        # Next upgrade cost (only if not maxed)
        if sect["array_level"] < sects.SECT_MAX_ARRAY_LEVEL:
            cost = sects.array_upgrade_cost(sect["array_level"])
            embed.add_field(
                name="Next Upgrade",
                value=f"→ Level {sect['array_level'] + 1} · cost {cost:,} 💎",
                inline=True,
            )

        # Array burst status
        now = datetime.now(timezone.utc)
        ready_in = sects.burst_ready_in(sect.get("last_burst_at"), now)
        burst_cost = sects.array_burst_cost(sect["array_level"])
        burst_pulse = sects.array_burst_pulse(sect["array_level"])
        burst_status = (
            f"🟢 Ready · {burst_cost:,} 💎 → +{burst_pulse} Stored Qi / member"
            if not ready_in else f"🟠 Cooling · {ready_in} left"
        )
        embed.add_field(name="Array Burst · 阵发", value=burst_status, inline=True)

        # Roster (top 15 by realm)
        roster = sorted(
            members, key=lambda m: (m["realm_tier"], m["realm_sub_stage"]), reverse=True
        )[:15]
        lines = []
        for m in roster:
            rank_tag = sects.SECT_RANK_LABELS.get(m["sect_rank"], m["sect_rank"])
            lines.append(
                f"• <@{m['user_id']}> — {rank_tag} · "
                f"{ui.realm_summary(m['realm_tier'], m['realm_sub_stage'])}"
            )
        embed.add_field(
            name="Roster · 名册",
            value="\n".join(lines) if lines else "No members",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    # ============================================================== /sect donate
    @app_commands.command(
        name="sect_donate",
        description="Donate spirit stones from your wallet to the sect treasury",
    )
    async def sect_donate(
        self, interaction: discord.Interaction, amount: int
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me or not me["sect_id"]:
            await self._refuse(interaction, "You must belong to a sect to donate.")
            return

        ok, reason = sects.validate_donate(amount, me["spirit_stones"])
        if not ok:
            await self._refuse(interaction, reason)
            return

        await self.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones-? WHERE id=?",
            (amount, me["id"]),
        )
        await self.bot.db.execute(
            "UPDATE sects SET treasury_stones=treasury_stones+? WHERE id=?",
            (amount, me["sect_id"]),
        )
        sect = await self._sect_of(me)

        embed = discord.Embed(
            title="💎 Donation · 捐献",
            description=(
                f"{interaction.user.mention} donated **{amount:,}** spirit stones "
                f"to **{sect['name']}**."
            ),
            color=ui.GOLD,
        )
        embed.add_field(name="Treasury · 灵石库", value=f"{sect['treasury_stones']:,} 💎", inline=True)
        embed.add_field(
            name="Your Wallet",
            value=f"{me['spirit_stones'] - amount:,} 💎",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    # ====================================================== /sect upgrade_array
    @app_commands.command(
        name="sect_upgrade_array",
        description="Upgrade the sect array (Patriarch only) — spends treasury stones",
    )
    async def sect_upgrade_array(self, interaction: discord.Interaction) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me or not me["sect_id"]:
            await self._refuse(interaction, "You must belong to a sect.")
            return
        sect = await self._sect_of(me)
        if not sect or sect["patriarch_id"] != me["id"]:
            await self._refuse(interaction, "Only the Patriarch may upgrade the array.")
            return

        ok, reason = sects.validate_upgrade(sect["array_level"], sect["treasury_stones"])
        if not ok:
            await self._refuse(interaction, reason)
            return

        cost = sects.array_upgrade_cost(sect["array_level"])
        new_level = sect["array_level"] + 1
        await self.bot.db.execute(
            "UPDATE sects SET array_level=?, treasury_stones=treasury_stones-? WHERE id=?",
            (new_level, cost, sect["id"]),
        )

        embed = discord.Embed(
            title="🔮 Array Upgraded · 阵法升级",
            description=(
                f"**{sect['name']}**'s array resonates with new power — "
                f"level {sect['array_level']} → **{new_level}**."
            ),
            color=ui.PURPLE,
        )
        embed.add_field(name="Cost · 消耗", value=f"{cost:,} 💎", inline=True)
        embed.add_field(
            name="New Bonus · 加成",
            value=f"+{sects.array_bonus_pct(new_level):.0f}% Qi",
            inline=True,
        )
        embed.add_field(
            name="Treasury · 灵石库",
            value=f"{sect['treasury_stones'] - cost:,} 💎",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    # ======================================================== /sect array_burst
    @app_commands.command(
        name="sect_array_burst",
        description="Trigger the array: pulses Stored Qi to every member (Patriarch only)",
    )
    async def sect_array_burst(self, interaction: discord.Interaction) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me or not me["sect_id"]:
            await self._refuse(interaction, "You must belong to a sect.")
            return
        sect = await self._sect_of(me)
        if not sect or sect["patriarch_id"] != me["id"]:
            await self._refuse(interaction, "Only the Patriarch may trigger the array.")
            return

        now = datetime.now(timezone.utc)
        ok, reason = sects.validate_burst(
            sect["array_level"], sect["treasury_stones"], sect.get("last_burst_at"), now
        )
        if not ok:
            await self._refuse(interaction, reason)
            return

        cost = sects.array_burst_cost(sect["array_level"])
        pulse = sects.array_burst_pulse(sect["array_level"])
        await self.bot.db.execute(
            "UPDATE sects SET treasury_stones=treasury_stones-?, last_burst_at=? WHERE id=?",
            (cost, now.isoformat(), sect["id"]),
        )
        await self.bot.db.execute(
            "UPDATE cultivators SET stored_qi_current="
            " MIN(stored_qi_max+stored_qi_max_bonus, stored_qi_current+?) WHERE sect_id=?",
            (pulse, sect["id"]),
        )
        members = await sect_members(self.bot.db, sect["id"])

        embed = discord.Embed(
            title="🔆 Array Burst · 阵法爆发",
            description=(
                f"**{sect['name']}**'s array flares with sect-wide power! "
                f"**+{pulse} Stored Qi** floods into **{len(members)} disciples**."
            ),
            color=ui.PURPLE,
        )
        embed.add_field(name="Cost · 消耗", value=f"{cost:,} 💎", inline=True)
        embed.add_field(
            name="Treasury · 灵石库",
            value=f"{sect['treasury_stones'] - cost:,} 💎",
            inline=True,
        )
        embed.add_field(
            name="Next Burst",
            value=f"~{sects.ARRAY_BURST_COOLDOWN.total_seconds() / 3600:g} hours",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    # ============================================================== /sect promote
    @app_commands.command(
        name="sect_promote",
        description="Promote a sect member by one rank (Patriarch only)",
    )
    async def sect_promote(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        await self._rank_change(interaction, member, promote=True)

    # ============================================================== /sect demote
    @app_commands.command(
        name="sect_demote",
        description="Demote a sect member (Patriarch only)",
    )
    async def sect_demote(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        await self._rank_change(interaction, member, promote=False)

    async def _rank_change(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        *,
        promote: bool,
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me or not me["sect_id"]:
            await self._refuse(interaction, "You must belong to a sect.")
            return
        sect = await self._sect_of(me)
        if not sect or sect["patriarch_id"] != me["id"]:
            await self._refuse(interaction, "Only the Patriarch may change ranks.")
            return

        target = await self._cultivator(member.id)
        if not target or target["sect_id"] != sect["id"]:
            await self._refuse(interaction, f"{member.mention} is not a member of your sect.")
            return

        actor_idx = sects.rank_index(me["sect_rank"])
        target_idx = sects.rank_index(target["sect_rank"])

        if promote:
            ok, reason = sects.validate_promote(actor_idx, target_idx)
            new_idx = sects.next_rank(target_idx)
            verb_en, verb_zh = "Promoted", "晋升"
            color = ui.GOLD
        else:
            ok, reason = sects.validate_demote(actor_idx, target_idx)
            new_idx = sects.prev_rank(target_idx)
            verb_en, verb_zh = "Demoted", "降阶"
            color = ui.CRIMSON

        if not ok or new_idx is None:
            await self._refuse(interaction, reason)
            return

        new_rank = sects.SECT_RANKS[new_idx]
        await self.bot.db.execute(
            "UPDATE cultivators SET sect_rank=? WHERE id=?",
            (new_rank, target["id"]),
        )

        embed = discord.Embed(
            title=f"🎖 {verb_en} · {verb_zh}",
            description=(
                f"{member.mention} has been {verb_en.lower()} to "
                f"**{sects.SECT_RANK_LABELS[new_rank]}** in **{sect['name']}**."
            ),
            color=color,
        )
        await interaction.response.send_message(embed=embed)

    # ============================================================== /sect expel
    @app_commands.command(
        name="sect_expel",
        description="Expel a member from the sect (Patriarch only)",
    )
    async def sect_expel(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me or not me["sect_id"]:
            await self._refuse(interaction, "You must belong to a sect.")
            return
        sect = await self._sect_of(me)
        if not sect or sect["patriarch_id"] != me["id"]:
            await self._refuse(interaction, "Only the Patriarch may expel members.")
            return

        target = await self._cultivator(member.id)
        if not target or target["sect_id"] != sect["id"]:
            await self._refuse(interaction, f"{member.mention} is not a member of your sect.")
            return

        actor_idx = sects.rank_index(me["sect_rank"])
        target_idx = sects.rank_index(target["sect_rank"])
        ok, reason = sects.validate_expel(actor_idx, target_idx)
        if not ok:
            await self._refuse(interaction, reason)
            return

        await self.bot.db.execute(
            "UPDATE cultivators SET sect_id=NULL, sect_rank='Outer Disciple'"
            " WHERE id=?",
            (target["id"],),
        )

        embed = discord.Embed(
            title="⚔ Expelled · 逐出宗门",
            description=(
                f"{member.mention} has been expelled from **{sect['name']}** "
                f"by Patriarch {interaction.user.mention}."
            ),
            color=ui.CRIMSON,
        )
        await interaction.response.send_message(embed=embed)
