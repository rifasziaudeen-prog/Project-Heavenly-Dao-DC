"""Dao Bonds — the player-to-player social core (review v2 pivot).

Dao Companions, sworn siblings, masters & disciples, rivals, and dual
cultivation partners are relationships between REAL server members. All
validation and math is deterministic (`core/dao_bonds.py`) — no LLM, no RNG.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import dao_bonds as bonds
from core import math as gm

BOND_TYPE_CHOICES = [
    app_commands.Choice(name=f"{label} ({value})", value=value)
    for value, label in bonds.BOND_TYPE_LABELS.items()
]


class DaoBondsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------- helpers
    async def _cultivator(self, user_id: int):
        return await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
        )

    async def _gender_role_map(self, guild_id: int) -> dict:
        cfg = await self.bot._guild_config(guild_id)
        return bonds.parse_gender_map(cfg.get("dao_role_to_gender"))

    @staticmethod
    def _gender_of(member: discord.Member, role_map: dict) -> str | None:
        return bonds.gender_of(role_map, member.roles)

    async def _pair_bond(self, a_id: int, b_id: int):
        """Any bond row between the pair (any status — the unique index makes
        one row per pair permanent)."""
        return await self.bot.db.fetchone(
            "SELECT * FROM dao_bonds WHERE"
            " (cultivator_a_id=? AND cultivator_b_id=?)"
            " OR (cultivator_a_id=? AND cultivator_b_id=?)",
            (a_id, b_id, b_id, a_id),
        )

    async def _active_bonds_for(self, cultivator_id: int) -> list:
        return await self.bot.db.fetchall(
            "SELECT * FROM dao_bonds WHERE status IN ('forming','active')"
            " AND (cultivator_a_id=? OR cultivator_b_id=?) ORDER BY id DESC",
            (cultivator_id, cultivator_id),
        )

    async def _bond_count(self, cultivator_id: int, bond_type: str) -> int:
        row = await self.bot.db.fetchone(
            "SELECT COUNT(*) AS c FROM dao_bonds"
            " WHERE status IN ('forming','active') AND bond_type=?"
            " AND (cultivator_a_id=? OR cultivator_b_id=?)",
            (bond_type, cultivator_id, cultivator_id),
        )
        return int(row["c"]) if row else 0

    async def _last_self_severance(self, cultivator_id: int):
        """Most recent bond THIS cultivator severed (status='severed',
        severed_by=them). Used to detect the fickle-rebond pattern."""
        return await self.bot.db.fetchone(
            "SELECT severed_at FROM dao_bonds WHERE status='severed'"
            " AND severed_by=? ORDER BY severed_at DESC LIMIT 1",
            (cultivator_id,),
        )

    async def _notify(self, member: discord.Member, embed: discord.Embed) -> bool:
        try:
            await member.send(embed=embed)
            return True
        except discord.HTTPException:
            return False

    # ============================================================== /dao_bond
    @app_commands.command(
        name="dao_bond",
        description="Propose a Dao Bond with another cultivator",
    )
    @app_commands.choices(bond_type=BOND_TYPE_CHOICES)
    async def dao_bond(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        bond_type: str,
    ) -> None:
        if interaction.user.id == target.id:
            await interaction.response.send_message(
                "You cannot bond with yourself — the Dao demands company, not mirrors.",
                ephemeral=True,
            )
            return
        me = await self._cultivator(interaction.user.id)
        them = await self._cultivator(target.id)
        if not me or not them:
            await interaction.response.send_message(
                "Both cultivators must `/register` before forming a bond.",
                ephemeral=True,
            )
            return

        existing = await self._pair_bond(me["id"], them["id"])
        if existing and existing["status"] == "severed":
            await interaction.response.send_message(
                "You two share a severed past — the Dao does not allow reforging "
                "bonds between former partners (yet).",
                ephemeral=True,
            )
            return

        role_map = await self._gender_role_map(interaction.guild_id)
        ok, reason = bonds.validate_bond_formation(
            self_gender=self._gender_of(interaction.user, role_map),
            other_gender=self._gender_of(target, role_map),
            bond_type=bond_type,
            self_tier=me["realm_tier"],
            other_tier=them["realm_tier"],
            active_count=await self._bond_count(me["id"], bond_type),
            existing_pair=existing is not None,
        )
        if not ok:
            embed = discord.Embed(
                title="Bond Refused · 天地不许", description=reason, color=ui.CRIMSON
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            cursor = await self.bot.db.execute(
                "INSERT INTO dao_bonds"
                " (cultivator_a_id, cultivator_b_id, initiator_id, bond_type)"
                " VALUES (?,?,?,?)",
                (me["id"], them["id"], me["id"], bond_type),
            )
        except sqlite3.IntegrityError:
            embed = discord.Embed(
                title="Bond Refused · 天地不许",
                description="A Dao Bond already exists between you two.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        label = bonds.BOND_TYPE_LABELS.get(bond_type, bond_type)

        # Fickle rebond: the severer chasing new romance within a week is
        # stigmatized — branded Fickle Heart and named publicly. Seed of the
        # demonic path (Phase 3).
        scandal = None
        last_severance = await self._last_self_severance(me["id"])
        if last_severance and bonds.is_fickle_rebond(
            bond_type, last_severance["severed_at"], severed_by_self=True
        ):
            await self.bot.db.execute(
                "UPDATE cultivators SET titles=? WHERE id=?",
                (ui.add_json_title(me["titles"], bonds.FICKLE_TITLE), me["id"]),
            )
            scandal = bonds.FICKLE_TITLE
        dm = discord.Embed(
            title=f"💌 Dao Bond Proposal · {label}",
            description=f"<@{interaction.user.id}> seeks to form a **{label}** bond with you.",
            color=ui.GOLD,
        )
        dm.add_field(
            name="Accept",
            value=f"`/dao_bond_accept @{interaction.user.display_name}`",
            inline=False,
        )
        dm.add_field(
            name="Decline",
            value=f"`/dao_bond_decline @{interaction.user.display_name}`",
            inline=False,
        )
        dm_sent = await self._notify(target, dm)

        embed = discord.Embed(
            title=f"💌 Bond Proposed · {label}",
            description=(
                f"You have proposed a **{label}** bond with {target.mention}.\n"
                "The Heaven records your intent."
            ),
            color=ui.GOLD,
        )
        embed.add_field(name="Status", value="Pending · awaiting their answer", inline=True)
        if not dm_sent:
            embed.add_field(
                name="Note",
                value="They have DMs closed — tell them to accept or decline.",
                inline=False,
            )
        if scandal:
            embed.add_field(
                name=f"🏷 Scandal · {scandal}",
                value=(
                    f"You severed a bond mere days ago, yet already chase new romance. "
                    f"The cultivation world brands you **{scandal}** — and the word spreads."
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    # ================================================== /dao_bond_accept
    @app_commands.command(
        name="dao_bond_accept",
        description="Accept a pending Dao Bond proposal",
    )
    async def dao_bond_accept(
        self, interaction: discord.Interaction, initiator: discord.Member
    ) -> None:
        await self._respond_to_proposal(interaction, initiator, accept=True)

    # ================================================== /dao_bond_decline
    @app_commands.command(
        name="dao_bond_decline",
        description="Decline a pending Dao Bond proposal",
    )
    async def dao_bond_decline(
        self, interaction: discord.Interaction, initiator: discord.Member
    ) -> None:
        await self._respond_to_proposal(interaction, initiator, accept=False)

    async def _respond_to_proposal(
        self, interaction: discord.Interaction, initiator: discord.Member, *, accept: bool
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        them = await self._cultivator(initiator.id)
        if not me or not them:
            await interaction.response.send_message(
                "Both cultivators must `/register` first.", ephemeral=True
            )
            return
        bond = await self.bot.db.fetchone(
            "SELECT * FROM dao_bonds WHERE status='forming' AND initiator_id=?"
            " AND ((cultivator_a_id=? AND cultivator_b_id=?)"
            "      OR (cultivator_a_id=? AND cultivator_b_id=?))",
            (them["id"], me["id"], them["id"], them["id"], me["id"]),
        )
        if not bond:
            await interaction.response.send_message(
                f"No pending proposal from {initiator.mention}.", ephemeral=True
            )
            return
        label = bonds.BOND_TYPE_LABELS.get(bond["bond_type"], bond["bond_type"])

        if accept:
            await self.bot.db.execute(
                "UPDATE dao_bonds SET status='active' WHERE id=?", (bond["id"],)
            )
            embed = discord.Embed(
                title="💞 Bond Formed · 道契已结",
                description=(
                    f"You and {initiator.mention} are now **{label}**. "
                    "The Heaven witnesses your oath."
                ),
                color=ui.GOLD,
            )
            dm = discord.Embed(
                title="💞 Bond Accepted · 道契已成",
                description=f"<@{interaction.user.id}> accepted your **{label}** bond.",
                color=ui.GOLD,
            )
        else:
            await self.bot.db.execute(
                "DELETE FROM dao_bonds WHERE id=?", (bond["id"],)
            )
            embed = discord.Embed(
                title="🌧 Proposal Declined · 缘断",
                description=f"You declined {initiator.mention}'s **{label}** proposal.",
                color=ui.CYAN,
            )
            dm = discord.Embed(
                title="🌧 Proposal Declined · 缘断",
                description=f"<@{interaction.user.id}> declined your **{label}** proposal.",
                color=ui.CYAN,
            )
        await self._notify(initiator, dm)
        await interaction.response.send_message(embed=embed)

    # ====================================================== /dao_bond_sever
    @app_commands.command(
        name="dao_bond_sever",
        description="Sever a Dao Bond — the drama will be public",
    )
    async def dao_bond_sever(
        self,
        interaction: discord.Interaction,
        partner: discord.Member,
        reason: str = "The Dao has grown distant.",
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        them = await self._cultivator(partner.id)
        if not me or not them:
            await interaction.response.send_message(
                "Both cultivators must `/register` first.", ephemeral=True
            )
            return
        bond = await self._pair_bond(me["id"], them["id"])
        if not bond or bond["status"] != "active":
            await interaction.response.send_message(
                "There is no active bond between you two to sever.", ephemeral=True
            )
            return

        fx = bonds.severance_effects(bond["bond_tier"])
        label = bonds.BOND_TYPE_LABELS.get(bond["bond_type"], bond["bond_type"])
        now = ui.now_str()
        # Severer (me): Heart Demon + negative karma
        await self.bot.db.execute(
            "UPDATE cultivators SET heart_demon_ratio=?, karma_points=karma_points+?"
            " WHERE id=?",
            (min(1.0, me["heart_demon_ratio"] + fx["heart_demon_both"]),
             fx["betrayer_karma"], me["id"]),
        )
        # Victim (them): Heart Demon + Betrayed title + 7-day rage buff
        await self.bot.db.execute(
            "UPDATE cultivators SET heart_demon_ratio=?, titles=?,"
            " rage_breakthrough_bonus_until=? WHERE id=?",
            (min(1.0, them["heart_demon_ratio"] + fx["heart_demon_both"]),
             ui.add_json_title(them["titles"], fx["rage_title"]),
             bonds.rage_until_str(), them["id"]),
        )
        await self.bot.db.execute(
            "UPDATE dao_bonds SET status='severed', severed_by=?, severed_at=?,"
            " severance_reason=?, severance_karma_impact=? WHERE id=?",
            (me["id"], now, reason, fx["betrayer_karma"], bond["id"]),
        )

        embed = discord.Embed(
            title="💔 Bond Severed · 道契已断",
            description=(
                f"<@{interaction.user.id}> has severed the **{label}** bond with "
                f"{partner.mention}.\n\n*“{reason}”*"
            ),
            color=ui.CRIMSON,
        )
        embed.add_field(
            name="Consequences",
            value=(
                f"Both cultivators gain **{fx['heart_demon_both']:.0%}** 心魔 (Heart Demon).\n"
                f"The severer loses **{abs(fx['betrayer_karma'])}** karma.\n"
                f"{partner.mention} receives the **{fx['rage_title']}** title and a "
                f"**+{fx['rage_bonus']:.0%}** breakthrough buff for {fx['rage_duration_days']} days "
                "(rage cultivation)."
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed)  # public drama

    # ============================================================ /dao_bonds
    @app_commands.command(name="dao_bonds", description="List your Dao Bonds")
    async def dao_bonds(self, interaction: discord.Interaction) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me:
            await interaction.response.send_message(
                "You have not `/register`ed yet.", ephemeral=True
            )
            return
        rows = await self._active_bonds_for(me["id"])
        if not rows:
            embed = discord.Embed(
                title="Dao Bonds · 道契",
                description="You walk the Dao alone. Use `/dao_bond @user` to forge ties.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed)
            return

        lines = []
        for bond in rows:
            partner_id = (
                bond["cultivator_a_id"]
                if bond["cultivator_b_id"] == me["id"]
                else bond["cultivator_b_id"]
            )
            partner = await self.bot.db.fetchone(
                "SELECT username FROM cultivators WHERE id=?", (partner_id,)
            )
            name = partner["username"] if partner else "Unknown"
            label = bonds.BOND_TYPE_LABELS.get(bond["bond_type"], bond["bond_type"])
            status_icon = "⏳" if bond["status"] == "forming" else "🔗"
            lines.append(
                f"{status_icon} **{name}** — {label} · tier {bond['bond_tier']} · "
                f"{bond['bond_points']} pts"
            )
        embed = discord.Embed(
            title="Dao Bonds · 道契", description="\n".join(lines), color=ui.GOLD
        )
        await interaction.response.send_message(embed=embed)

    # ======================================================== /dual_cultivate
    @app_commands.command(
        name="dual_cultivate",
        description="Cultivate together with your Dao Companion (both must consent)",
    )
    async def dual_cultivate(
        self, interaction: discord.Interaction, partner: discord.Member
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        them = await self._cultivator(partner.id)
        if not me or not them:
            await interaction.response.send_message(
                "Both cultivators must `/register` first.", ephemeral=True
            )
            return
        bond = await self._pair_bond(me["id"], them["id"])
        if not bond or bond["status"] != "active":
            await interaction.response.send_message(
                "There is no active Dao Bond between you two.", ephemeral=True
            )
            return
        if bond["bond_type"] not in (bonds.DAO_COMPANION, bonds.DUAL_CULTIVATION):
            await interaction.response.send_message(
                "Dual cultivation requires a **道侣 Dao Companion** or "
                "**双修伴侣 Dual Cultivation Partner** bond.",
                ephemeral=True,
            )
            return
        if bond["bond_tier"] < bonds.DUAL_MIN_BOND_TIER:
            await interaction.response.send_message(
                f"This bond must reach **tier {bonds.DUAL_MIN_BOND_TIER}** before dual "
                "cultivation opens (keep bonding through shared activities).",
                ephemeral=True,
            )
            return
        last = ui.parse_db_time(bond["last_dual_cultivation_at"])
        if last:
            elapsed = (ui.now_utc() - last).total_seconds()
            cooldown = bonds.DUAL_COOLDOWN_HOURS * 3600
            if elapsed < cooldown:
                await interaction.response.send_message(
                    f"The yin-yang energies need rest — cultivate again in "
                    f"**{ui.format_duration(cooldown - elapsed)}**.",
                    ephemeral=True,
                )
                return

        label = bonds.BOND_TYPE_LABELS.get(bond["bond_type"], bond["bond_type"])
        embed = discord.Embed(
            title=f"💫 Dual Cultivation · {label}",
            description=(
                f"{interaction.user.mention} and {partner.mention} prepare to align "
                "their 阴阳 (yin-yang) energies.\n\n"
                "**Both cultivators must press Consent.**"
            ),
            color=ui.PURPLE,
        )
        view = DualCultivateView(self, {interaction.user.id, partner.id}, bond["id"])
        await interaction.response.send_message(embed=embed, view=view)

    async def _execute_dual(
        self, interaction: discord.Interaction, bond_id: int, pair_ids: set[int]
    ) -> None:
        bond = await self.bot.db.fetchone(
            "SELECT * FROM dao_bonds WHERE id=?", (bond_id,)
        )
        if not bond or bond["status"] != "active":
            await interaction.edit_original_response(
                content="The bond is no longer active.", embed=None, view=None
            )
            return
        a = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE id=?", (bond["cultivator_a_id"],)
        )
        b = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE id=?", (bond["cultivator_b_id"],)
        )
        if not a or not b:
            await interaction.edit_original_response(
                content="A cultivator is missing.", embed=None, view=None
            )
            return

        synergy = bonds.calculate_bond_synergy(
            dict(a), dict(b), a["karma_points"], b["karma_points"],
            a["realm_tier"], b["realm_tier"], bond["bond_tier"],
        )
        gain_a = int(
            gm.calculate_qi_gain(a["realm_tier"], a["comprehension"],
                                 source="dual_cultivation")
            * min(synergy, bonds.DUAL_QI_BONUS_CAP)
        )
        gain_b = int(
            gm.calculate_qi_gain(b["realm_tier"], b["comprehension"],
                                 source="dual_cultivation")
            * min(synergy, bonds.DUAL_QI_BONUS_CAP)
        )
        now = ui.now_str()

        # Atomic cooldown gate: only ONE ritual may consume the window, even if
        # two consent flows overlap (each /dual_cultivate makes its own message).
        # A conditional UPDATE + rowcount check prevents double-application.
        cutoff = (ui.now_utc() - timedelta(hours=bonds.DUAL_COOLDOWN_HOURS)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        gate = await self.bot.db.execute(
            "UPDATE dao_bonds SET last_dual_cultivation_at=? WHERE id=? AND"
            " (last_dual_cultivation_at IS NULL OR last_dual_cultivation_at <= ?)",
            (now, bond_id, cutoff),
        )
        if gate.rowcount != 1:
            await interaction.edit_original_response(
                content="The yin-yang energies still need rest — the cooldown has not elapsed.",
                embed=None,
                view=None,
            )
            return

        await self.bot.db.execute(
            "UPDATE cultivators SET qi_current=qi_current+?,"
            " heart_demon_ratio=? WHERE id=?",
            (gain_a, max(0.0, a["heart_demon_ratio"] - bonds.DUAL_HEART_DEMON_REDUCTION),
             a["id"]),
        )
        await self.bot.db.execute(
            "UPDATE cultivators SET qi_current=qi_current+?,"
            " heart_demon_ratio=? WHERE id=?",
            (gain_b, max(0.0, b["heart_demon_ratio"] - bonds.DUAL_HEART_DEMON_REDUCTION),
             b["id"]),
        )
        new_points = bond["bond_points"] + bonds.DUAL_BOND_POINTS
        new_tier = bonds.bond_tier_from_points(new_points)
        events = ui.parse_json_list(bond["shared_events"]) + [
            {"type": "dual_cultivation", "date": now, "qi_shared": gain_a + gain_b}
        ]
        await self.bot.db.execute(
            "UPDATE dao_bonds SET bond_points=?, bond_tier=?,"
            " dual_cultivation_count=dual_cultivation_count+1,"
            " last_dual_cultivation_at=?, shared_events=? WHERE id=?",
            (new_points, new_tier, now, json.dumps(events), bond_id),
        )

        embed = discord.Embed(
            title="💫 Yin-Yang Resonance · 阴阳共鸣",
            description=(
                "The twin energies harmonize — a burst of high-purity qi floods "
                "both cultivators, and 心魔 (Heart Demons) recede."
            ),
            color=ui.PURPLE,
        )
        embed.add_field(
            name=f"{a['username']} · {b['username']}",
            value=(f"+{ui.format_qi(gain_a)} & +{ui.format_qi(gain_b)} · "
                   f"Heart Demon −{bonds.DUAL_HEART_DEMON_REDUCTION:.0%}"),
            inline=False,
        )
        embed.add_field(
            name="Bond Progress",
            value=f"tier {bond['bond_tier']} → {new_tier} · {new_points} pts",
            inline=True,
        )
        embed.add_field(
            name="Synergy",
            value=f"{synergy:.2f}x",
            inline=True,
        )
        embed.add_field(
            name="Cooldown",
            value=ui.format_duration(bonds.DUAL_COOLDOWN_HOURS * 3600),
            inline=True,
        )
        await interaction.edit_original_response(embed=embed, view=None)


class DualCultivateView(discord.ui.View):
    def __init__(self, cog: DaoBondsCog, pair_ids: set[int], bond_id: int) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.pair_ids = pair_ids
        self.bond_id = bond_id
        self.consented: set[int] = set()

    @discord.ui.button(label="Consent · 同意", style=discord.ButtonStyle.success, emoji="💫")
    async def consent(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id not in self.pair_ids:
            await interaction.response.send_message(
                "This ritual is not yours to join.", ephemeral=True
            )
            return
        if interaction.user.id in self.consented:
            await interaction.response.send_message(
                "You have already consented.", ephemeral=True
            )
            return
        self.consented.add(interaction.user.id)
        await interaction.response.defer()
        if len(self.consented) >= 2:
            self.stop()
            await self.cog._execute_dual(interaction, self.bond_id, self.pair_ids)
        else:
            remaining = self.pair_ids - self.consented
            waiting = " ".join(f"<@{uid}>" for uid in remaining)
            await interaction.edit_original_response(
                content=f"💫 {len(self.consented)}/2 consented — waiting on {waiting}…",
                view=self,
            )

    @discord.ui.button(label="Cancel · 取消", style=discord.ButtonStyle.danger)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id not in self.pair_ids:
            await interaction.response.send_message(
                "This ritual is not yours to join.", ephemeral=True
            )
            return
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(
            content="🌫 The dual cultivation ritual was called off.", embed=None, view=None
        )
