"""Contendance (争道) combat cog — /contend, /battle, /learn, /techniques, /reroll.

Thin glue over core/combat.py: sessions and Discord views live here, all math
lives in the core module. Duel intents are chosen in private DMs (blind, per
the design), round revelations are posted publicly to the channel.
"""
from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import combat as core_cbt
from core import dao_laws as core_dl
from core import items as core_items
from core import math as gm
from db.queries import (
    active_artifact,
    get_or_create_cultivator,
    spend_artifact_energy,
)

_EMOJI = {"technique": "⚔️", "unfold": "☯️", "artifact": "🗡️", "pill": "💊",
          "retreat": "🏳️", "pass": "⏳"}
_KIND_LABEL = {"technique": "Technique", "unfold": "Unfold Law", "artifact": "Artifact Parry",
               "pill": "Pill", "retreat": "Retreat", "pass": "No Action"}

_INTENT = "intent"
_ACCEPT = "accept"


# --------------------------------------------------------------------------- views
class _AcceptView(discord.ui.View):
    """Public challenge: the target (or anyone in a duel) accepts/declines."""

    def __init__(self, cog, duel_key: tuple, challenger_id: int) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.duel_key = duel_key
        self.challenger_id = challenger_id
        self.accepted_by: int | None = None

    async def _refund_wager(self, duel) -> None:
        """Both fighters already paid at /contend — give it back on a non-fight."""
        if not duel.wager:
            return
        ids = (duel.cultivator(duel.p1_uid)["id"], duel.cultivator(duel.p2_uid)["id"])
        await self.cog.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id IN (?,?)",
            (duel.wager, *ids),
        )

    @discord.ui.button(label="⚔️ Accept the Duel", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        duel = self.cog.duels.get(self.duel_key)
        if not duel or duel.state != _ACCEPT:
            await interaction.response.send_message("This challenge has already been resolved.", ephemeral=True)
            return
        if interaction.user.id not in (duel.p1_uid, duel.p2_uid):
            await interaction.response.send_message("Only the challenged cultivator may accept.", ephemeral=True)
            return
        self.accepted_by = interaction.user.id
        await self.cog._begin_duel(self.duel_key, interaction)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        duel = self.cog.duels.get(self.duel_key)
        if not duel:
            await interaction.response.send_message("Challenge already gone.", ephemeral=True)
            return
        if interaction.user.id not in (duel.p1_uid, duel.p2_uid):
            await interaction.response.send_message("Only the challenged cultivator may decline.", ephemeral=True)
            return
        await self._refund_wager(duel)
        await interaction.response.edit_message(content="❌ The challenge was declined. Wagers refunded.", view=None)
        self.cog.duels.pop(self.duel_key, None)
        self.stop()

    async def on_timeout(self) -> None:
        """Challenge unanswered — refund both stakes and free the fighters."""
        duel = self.cog.duels.pop(self.duel_key, None)
        if not duel or duel.state != _ACCEPT:
            return
        duel.state = "cancelled"
        await self._refund_wager(duel)
        try:
            await duel.channel.send("⏳ The challenge expired unanswered. Wagers refunded.")
        except Exception:
            pass
        self.stop()


class _IntentView(discord.ui.View):
    """Blind intent picker (one per player, sent via DM)."""

    def __init__(self, cog, key: tuple, player_id: int, options: list[discord.SelectOption],
                 cost_hint: str, can_burn: bool, burn_cost_qi: int, timeout: float = 120.0) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog
        self.key = key
        self.player_id = player_id
        self.committed = False

        select = discord.ui.Select(
            placeholder=f"Choose your intent · {cost_hint}",
            options=options or [discord.SelectOption(label="🏳️ Retreat", value="retreat")],
            min_values=1, max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

        burn_label = f"🔥 Burn Base (+100 Stored Qi · costs {burn_cost_qi:,} dantian Qi)"
        self.burn = discord.ui.Button(label=burn_label, style=discord.ButtonStyle.danger, disabled=not can_burn)
        self.burn.callback = self._on_burn
        self.add_item(self.burn)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.player_id or self.committed:
            await interaction.response.send_message("You may only commit your own intent once.", ephemeral=True)
            return
        value = interaction.data["values"][0]
        session = self.cog._session_for(self.key)
        if session is None:
            await interaction.response.send_message("This combat has ended.", ephemeral=True)
            return
        session.pending[interaction.user.id] = value
        self.committed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"{_EMOJI.get(value, '⚔️')} **Intent committed.** Awaiting the clash…", view=self)
        await self.cog._maybe_resolve(self.key)

    async def _on_burn(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.player_id or self.committed:
            return
        session = self.cog._session_for(self.key)
        if session is None:
            return
        result = await self.cog._do_burn(self.key, interaction.user.id, session)
        if result is False:
            return  # burn failed — keep the view live
        # Burn succeeded; the intent still needs choosing.
        await interaction.response.edit_message(
            content=f"🔥 Base burned! **+{core_cbt.BURN_STORED_QI_GAIN} Stored Qi** — now choose your intent.",
            view=self,
        )


# --------------------------------------------------------------------------- sessions
class CombatSession:
    """Shared duel/battle state (in-memory; lost on restart — acceptable v1)."""

    def __init__(self, key: tuple, guild_id: int, channel) -> None:
        self.key = key
        self.guild_id = guild_id
        self.channel = channel
        self.state = _ACCEPT           # accept -> intent -> resolving -> ended
        self.round = 0
        self.timer: asyncio.Task | None = None
        self.pending: dict[int, str] = {}   # player user_id -> select value
        self.hp: dict[int, int] = {}
        self.dao_heart: dict[int, int] = {}
        self.burn_count: dict[int, int] = {}
        self.result: dict | None = None

    def both_committed(self) -> bool:
        return len(self.pending) >= 2 and self.state == _INTENT

    def is_player(self, user_id: int) -> bool:
        return user_id in self.player_ids()


class DuelSession(CombatSession):
    def __init__(self, key: tuple, guild_id: int, channel, p1, p2, wager: int = 0) -> None:
        super().__init__(key, guild_id, channel)
        self.p1 = p1            # dict cultivator (challenger)
        self.p2 = p2
        self.p1_uid = p1["user_id"]
        self.p2_uid = p2["user_id"]
        self.wager = wager
        self.state = _ACCEPT
        for p in (p1, p2):
            self.hp[p["id"]] = core_cbt.hp_max(p["realm_tier"])
            self.dao_heart[p["id"]] = core_cbt.DAO_HEART_MAX
            self.burn_count[p["id"]] = 0

    def player_ids(self) -> tuple:
        return (self.p1_uid, self.p2_uid)

    def cultivator(self, user_id: int) -> dict:
        return self.p1 if self.p1_uid == user_id else self.p2


class BattleSession(CombatSession):
    def __init__(self, key: tuple, guild_id: int, channel, player, beast: dict) -> None:
        super().__init__(key, guild_id, channel)
        self.player = player
        self.p_uid = player["user_id"]
        self.beast = beast
        self.beast_hp = int(beast["hp"])
        self.beast_round = 0
        self.state = _INTENT
        for p in (player,):
            self.hp[p["id"]] = core_cbt.hp_max(p["realm_tier"])
            self.dao_heart[p["id"]] = core_cbt.DAO_HEART_MAX
            self.burn_count[p["id"]] = 0

    def player_ids(self) -> tuple:
        return (self.p_uid,)

    def cultivator(self, user_id: int) -> dict:
        return self.player


# --------------------------------------------------------------------------- cog
class CombatCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.duels: dict[tuple, DuelSession] = {}
        self.battles: dict[tuple, BattleSession] = {}

    # ---------------------------------------------------------------- helpers
    async def _cultivator(self, user_id: int) -> dict | None:
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
        )
        return dict(row) if row else None

    def _session_for(self, key: tuple):
        return self.duels.get(key) or self.battles.get(key)

    def _player_in_fight(self, user_id: int) -> bool:
        for session in list(self.duels.values()) + list(self.battles.values()):
            if session.state != "ended" and user_id in session.player_ids():
                return True
        return False

    async def _learned_techniques(self, cultivator_id: int) -> list[dict]:
        rows = await self.bot.db.fetchall(
            "SELECT ct.*, t.name, t.name_zh, t.quality, t.law_affinity, t.base_damage, t.stored_qi_cost"
            " FROM cultivator_techniques ct JOIN techniques t ON t.id = ct.technique_id"
            " WHERE ct.cultivator_id=? ORDER BY t.quality, t.base_damage",
            (cultivator_id,),
        )
        return [dict(r) for r in rows]

    async def _law_ranks(self, cultivator_id: int) -> dict[str, float]:
        rows = await self.bot.db.fetchall(
            "SELECT l.name, cl.mastery_percentage FROM cultivator_laws cl"
            " JOIN dao_laws l ON l.id = cl.law_id WHERE cl.cultivator_id=?",
            (cultivator_id,),
        )
        return {r["name"]: float(r["mastery_percentage"]) for r in rows}

    async def _parry_value(self, cultivator_id: int) -> int:
        rows = await self.bot.db.fetchall(
            "SELECT effect_data FROM items WHERE owner_id=? AND is_equipped=1 AND item_type='Weapon'",
            (cultivator_id,),
        )
        bonus = 0
        for r in rows:
            eff = core_items.parse_effect_data(r["effect_data"])
            if eff.get("type") == "stat_buff":
                bonus += int(eff.get("amount", 0))
        return min(core_cbt.ARTIFACT_PARRY_CAP,
                   core_cbt.ARTIFACT_PARRY_BASE + bonus)

    async def _intent_options(self, cultivator: dict, is_battle: bool = False) -> tuple[list[discord.SelectOption], dict]:
        """Build the intent select options + the resolver data for one player."""
        techs = await self._learned_techniques(cultivator["id"])
        laws = await self._law_ranks(cultivator["id"])
        parry = await self._parry_value(cultivator["id"])

        options: list[discord.SelectOption] = []
        # Learned techniques
        for t in techs:
            rank = core_cbt.technique_rank(t["mastery_progress"])
            cost = core_cbt.technique_cost(t, rank)
            q = t["quality"]
            options.append(discord.SelectOption(
                label=f"{_EMOJI['technique']} {t['name']} ({cost} SQ)",
                description=f"{q} · Rank {rank} · {t.get('entries') or 'no entries'}",
                value=f"tech:{t['technique_id']}",
            ))
        # Always-available basic strike
        options.append(discord.SelectOption(
            label="⚔️ Basic Strike (5 SQ)", description="A raw, formless blow",
            value="basic",
        ))
        # Unfold laws (only those with at least rank 1)
        if laws:
            for name, mastery in laws.items():
                if core_dl.law_rank(mastery) < 1:
                    continue
                options.append(discord.SelectOption(
                    label=f"☯️ Unfold {name} ({core_cbt.LAW_UNFOLD_COST} SQ)",
                    description=f"Rank {core_dl.law_rank(mastery)} · {core_dl.law_resistance(mastery):.0%} resist",
                    value=f"law:{name}",
                ))
        active = await active_artifact(self.bot.db, cultivator["id"])
        if active:
            ab = active["ability"]
            options.append(discord.SelectOption(
                label=f"🗡️ Artifact: {ab.get('name', 'Active')} ({core_cbt.ARTIFACT_COST} SQ)",
                description=(f"Strike with the active + parry (energy "
                             f"{active['energy']}/{active['energy_max']})"),
                value="artifact",
            ))
        options.append(discord.SelectOption(
            label=f"🗡️ Artifact Parry ({core_cbt.ARTIFACT_COST} SQ)",
            description=f"Block incoming damage (parry {parry})", value="artifact",
        ))
        options.append(discord.SelectOption(
            label="💊 Pill", description="Restore Stored Qi from inventory", value="pill",
        ))
        if not is_battle:
            options.append(discord.SelectOption(label="🏳️ Retreat", description="Forfeit this duel", value="retreat"))

        return options, {"techs": techs, "laws": laws, "parry": parry, "active": active}

    def _build_intent(self, value: str, cultivator: dict, data: dict) -> dict | None:
        """Turn a select value + resolver data into a core intent dict."""
        stats = {"physique": int(cultivator.get("physique", 10)),
                 "spirit": int(cultivator.get("spirit", 10))}
        base = {"stats": stats, "laws": data["laws"]}

        if value == "basic":
            return {**base, "kind": "technique",
                    "technique": {"base_damage": 8, "stored_qi_cost": 5, "law_affinity": None},
                    "entries": [], "rank": 1}
        if value.startswith("tech:"):
            tid = int(value.split(":", 1)[1])
            t = next((x for x in data["techs"] if x["technique_id"] == tid), None)
            if not t:
                return None
            return {**base, "kind": "technique",
                    "technique": {"base_damage": t["base_damage"],
                                  "stored_qi_cost": t["stored_qi_cost"],
                                  "law_affinity": t["law_affinity"]},
                    "entries": list(json.loads(t.get("entries") or "[]")),
                    "rank": core_cbt.technique_rank(t["mastery_progress"])}
        if value.startswith("law:"):
            name = value.split(":", 1)[1]
            mastery = data["laws"].get(name, 0.0)
            return {**base, "kind": "unfold",
                    "law": {"name": name, "rank": core_dl.law_rank(mastery), "mastery": mastery}}
        if value == "artifact":
            intent = {**base, "kind": "artifact", "parry": data["parry"]}
            active = data.get("active")
            if active and active["energy"] >= active["energy_cost"]:
                # A charged active sharpens the guard too.
                intent["parry"] = data["parry"] + core_items.ARTIFACT_ACTIVE_PARRY_BONUS
                intent["active_power"] = core_items.artifact_active_power(
                    active["ability"], stats)
                intent["energy_cost"] = active["energy_cost"]
                intent["active_item_id"] = active["item_id"]
            return intent
        if value == "pill":
            return {**base, "kind": "pill"}
        if value == "retreat":
            return {**base, "kind": "retreat"}
        return None

    def _intent_cost(self, intent: dict) -> int:
        if intent["kind"] == "technique":
            mods = core_cbt.entry_modifiers(intent.get("entries", []))
            return int(core_cbt.technique_cost(intent["technique"], intent["rank"]) * mods["cost_mult"])
        if intent["kind"] == "unfold":
            return core_cbt.LAW_UNFOLD_COST
        if intent["kind"] == "artifact":
            return core_cbt.ARTIFACT_COST
        return 0

    async def _do_burn(self, key: tuple, user_id: int, session) -> bool:
        cult = session.cultivator(user_id)
        if cult["qi_current"] < gm.burn_cost(cult["realm_tier"]):
            return False
        count = session.burn_count.get(user_id, 0) + 1
        session.burn_count[user_id] = count
        # The base burn + its Heart Demon consequence commit as one unit.
        async with self.bot.db.transaction():
            await self.bot.db.execute(
                "UPDATE cultivators SET qi_current=qi_current-?, stored_qi_current="
                " MIN(stored_qi_max+stored_qi_max_bonus, stored_qi_current+?) WHERE id=?",
                (gm.burn_cost(cult["realm_tier"]), core_cbt.BURN_STORED_QI_GAIN, cult["id"]),
            )
            consequence = gm.burn_consequence(count, cult["realm_tier"], erasure_enabled=True)
            if consequence["heart_demon_delta"]:
                await self.bot.db.execute(
                    "UPDATE cultivators SET heart_demon_ratio=MIN(1.0, heart_demon_ratio+?) WHERE id=?",
                    (consequence["heart_demon_delta"], cult["id"]),
                )
        # Random consequence rolls happen AFTER the commit — they end the fight
        # rather than being part of the atomic burn itself.
        if consequence["retreat_or_deviation"] and random.random() < 0.5:
            await self._force_retreat(session, user_id, reason="burn_deviation")
            return False
        if consequence["erasure_roll"] and random.random() < 0.5:
            await self._burn_erasure(cult)
        return True

    async def _force_retreat(self, session, user_id: int, reason: str) -> None:
        """Burn deviation forces the fighter out — a duel is a loss for them, a
        battle ends without victory. (Previously routed to a non-existent
        `_end_combat`; this would have crashed the deviation branch.)"""
        if isinstance(session, BattleSession):
            await self._end_battle(session, won=False, reason=reason)
        else:
            await self._end_duel(session, defeated_uid=user_id, reason=reason)

    async def _burn_erasure(self, cult: dict) -> None:
        """The final burn threshold can trigger Heavenly Dao Erasure (tier 8+)."""
        await self.bot.db.execute(
            "UPDATE cultivators SET realm_tier=1, realm_sub_stage=1, qi_current=0,"
            " qi_capacity=? WHERE id=?",
            (gm.qi_capacity_for(1) + cult.get("transcendence_capacity_bonus", 0), cult["id"]),
        )

    # ------------------------------------------------------------- /contend
    @app_commands.command(name="contend", description="Challenge a cultivator to a Contendance duel")
    async def contend(self, interaction: discord.Interaction, opponent: discord.Member,
                      wager: int = 0) -> None:
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You cannot duel yourself.", ephemeral=True)
            return
        if self._player_in_fight(interaction.user.id):
            await interaction.response.send_message("You are already in a fight!", ephemeral=True)
            return
        if self._player_in_fight(opponent.id):
            await interaction.response.send_message(f"{opponent.display_name} is already in a fight!", ephemeral=True)
            return
        me = await self._cultivator(interaction.user.id)
        them = await self._cultivator(opponent.id)
        if not me or not them:
            await interaction.response.send_message("Both fighters must be `/register`ed.", ephemeral=True)
            return
        if wager < 0:
            await interaction.response.send_message("Wager cannot be negative.", ephemeral=True)
            return
        if wager and (me["spirit_stones"] < wager or them["spirit_stones"] < wager):
            await interaction.response.send_message(
                f"Both fighters must hold at least **{wager:,} 💎** to wager that amount.", ephemeral=True)
            return
        if wager:
            await self.bot.db.execute(
                "UPDATE cultivators SET spirit_stones=spirit_stones-? WHERE id IN (?,?)",
                (wager, me["id"], them["id"]),
            )

        key = (interaction.guild_id, interaction.user.id, opponent.id)
        self.duels[key] = DuelSession(key, interaction.guild_id, interaction.channel,
                                      me, them, wager=wager)
        embed = discord.Embed(
            title="⚔️ Contendance Challenge · 争道之约",
            description=(f"{interaction.user.mention} challenges {opponent.mention} to a **Contendance duel**!\n"
                         f"Realm {me['realm_tier']} vs Realm {them['realm_tier']} · "
                         f"{f'Wager: **{wager:,} 💎** each' if wager else 'Honor only'}"),
            color=ui.GOLD,
        )
        view = _AcceptView(self, key, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    async def _begin_duel(self, key: tuple, interaction: discord.Interaction) -> None:
        duel = self.duels[key]
        duel.state = _INTENT
        embed = discord.Embed(
            title="⚔️ The Duel Begins · 对决开始",
            description="Both cultivators must now **choose their intent in private** — Stored Qi is spent per round.",
            color=ui.PURPLE,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        await self._start_round(duel)

    # --------------------------------------------------------------- rounds
    async def _start_round(self, session: CombatSession) -> None:
        session.state = _INTENT
        session.round += 1
        session.pending = {}
        if session.timer:
            session.timer.cancel()
        session.timer = asyncio.create_task(self._round_clock(session))

        for uid in session.player_ids():
            await self._send_intent(session, uid)

    async def _send_intent(self, session: CombatSession, user_id: int) -> None:
        cult = session.cultivator(user_id)
        is_battle = isinstance(session, BattleSession)
        options, data = await self._intent_options(cult, is_battle=is_battle)
        row = await self.bot.db.fetchone(
            "SELECT stored_qi_current, stored_qi_max, stored_qi_max_bonus, qi_current, realm_tier FROM cultivators WHERE id=?",
            (cult["id"],),
        )
        sq = row["stored_qi_current"] if row else 0
        sq_max = gm.stored_qi_effective_max(cult.get("stored_qi_max", 100), cult.get("stored_qi_max_bonus", 0))
        qi = row["qi_current"] if row else 0
        can_burn = core_cbt.can_burn(qi, cult["realm_tier"])
        burn_qi = gm.burn_cost(cult["realm_tier"])

        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            dm = await user.create_dm()
        except discord.HTTPException:
            try:
                await session.channel.send(
                    f"<@{user_id}> — open your DMs so you can choose your intent in private! "
                    f"Round {session.round} will auto-resolve shortly."
                )
            except Exception:
                pass
            return

        embed = discord.Embed(
            title=f"Round {session.round} · Choose Your Intent",
            description=(f"**Stored Qi**: {sq}/{sq_max} · **HP**: {session.hp.get(cult['id'], 0)}"
                         f" · **Dao Heart**: {session.dao_heart.get(cult['id'], 0)}\n"
                         "Pick ONE action — your opponent cannot see it. Stored Qi is spent on commit."),
            color=ui.CYAN,
        )
        view = _IntentView(self, session.key, user_id, options,
                           cost_hint=f"Round {session.round}",
                           can_burn=can_burn, burn_cost_qi=burn_qi)
        await dm.send(embed=embed, view=view)

    async def _round_clock(self, session: CombatSession) -> None:
        await asyncio.sleep(core_cbt.INTENT_WINDOW_SECONDS)
        if session.state == _INTENT:
            await self._resolve_round(session)

    async def _maybe_resolve(self, key: tuple) -> None:
        session = self._session_for(key)
        if session and session.both_committed():
            await self._resolve_round(session)

    # ------------------------------------------------------------- resolve
    async def _resolve_round(self, session: CombatSession) -> None:
        if session.state != _INTENT or session.result is not None:
            return
        session.state = "resolving"
        if session.timer:
            session.timer.cancel()

        is_battle = isinstance(session, BattleSession)
        if is_battle:
            await self._resolve_battle_round(session)
        else:
            await self._resolve_duel_round(session)

    async def _spend_intent(self, session: CombatSession, user_id: int, intent: dict) -> None:
        cult = session.cultivator(user_id)
        # Stored Qi, artifact energy, mastery progress, and any pill consumed
        # all land as ONE unit — a crash mid-round can't charge the cost and
        # skip the effect (or vice versa).
        async with self.bot.db.transaction():
            cost = self._intent_cost(intent)
            if cost > 0:
                await self.bot.db.execute(
                    "UPDATE cultivators SET stored_qi_current=MAX(0, stored_qi_current-?) WHERE id=?",
                    (cost, cult["id"]),
                )
            # Artifact active: spend spirit energy on activation.
            if intent["kind"] == "artifact" and intent.get("energy_cost") and intent.get("active_item_id"):
                await spend_artifact_energy(
                    self.bot.db, intent["active_item_id"], intent["energy_cost"],
                    datetime.now(timezone.utc).isoformat(),
                )
            # Technique mastery progress + pill consumption
            if intent["kind"] == "technique" and intent.get("technique_id"):
                await self.bot.db.execute(
                    "UPDATE cultivator_techniques SET mastery_progress=MIN(100.0, mastery_progress+?),"
                    " times_used=times_used+1 WHERE cultivator_id=? AND technique_id=?",
                    (core_cbt.TECHNIQUE_MASTERY_PER_USE, cult["id"], intent["technique_id"]),
                )
            if intent["kind"] == "pill":
                await self._consume_stored_qi_pill(cult)

    async def _consume_stored_qi_pill(self, cult: dict) -> None:
        row = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND quantity>0 AND"
            " effect_data LIKE '%stored_qi_restore%' ORDER BY id LIMIT 1",
            (cult["id"],),
        )
        if not row:
            return
        eff = core_items.parse_effect_data(row["effect_data"])
        amount = int(eff.get("amount", 0))
        if row["quantity"] <= 1:
            await self.bot.db.execute("DELETE FROM items WHERE id=?", (row["id"],))
        else:
            await self.bot.db.execute("UPDATE items SET quantity=quantity-1 WHERE id=?", (row["id"],))
        await self.bot.db.execute(
            "UPDATE cultivators SET stored_qi_current=MIN(stored_qi_max+stored_qi_max_bonus, stored_qi_current+?) WHERE id=?",
            (amount, cult["id"]),
        )

    async def _build_intents_for(self, session: CombatSession, user_id: int, value: str) -> dict | None:
        cult = session.cultivator(user_id)
        _, data = await self._intent_options(cult, is_battle=isinstance(session, BattleSession))
        return self._build_intent(value, cult, data)

    async def _resolve_duel_round(self, duel: DuelSession) -> None:
        values = {uid: duel.pending.get(uid, "pass") for uid in duel.player_ids()}
        intents = {}
        for uid, value in values.items():
            cult = duel.cultivator(uid)
            _, data = await self._intent_options(cult)
            intent = self._build_intent(value, cult, data)
            intent["technique_id"] = self._technique_id_of(value, data)
            intents[uid] = intent
            await self._spend_intent(duel, uid, intent)

        a_intent, b_intent = intents[duel.p1_uid], intents[duel.p2_uid]
        outcome = core_cbt.resolve_round(a_intent, b_intent,
                                         random.randint(1, 20), random.randint(1, 20))

        # Apply damage / dao heart
        d20a_power_note = ""
        dmg_p1 = outcome["damage_a"]
        dmg_p2 = outcome["damage_b"]
        self._apply_hp(duel, duel.p1_uid, dmg_p1)
        self._apply_hp(duel, duel.p2_uid, dmg_p2)

        await self._post_round_embed(duel, a_intent, b_intent, outcome)

        ended = self._check_end(duel)
        if ended:
            await self._end_duel(duel, **ended)
            return
        await self._start_round(duel)

    def _technique_id_of(self, value: str, data: dict) -> int | None:
        if value.startswith("tech:"):
            return int(value.split(":", 1)[1])
        return None

    def _apply_hp(self, session: CombatSession, user_id: int, damage: int) -> None:
        cult = session.cultivator(user_id)
        session.hp[cult["id"]] = max(0, session.hp.get(cult["id"], 0) - damage)

    async def _post_round_embed(self, session: CombatSession, a_intent: dict, b_intent: dict,
                                outcome: dict) -> None:
        p1, p2 = session.player_ids()
        cult1, cult2 = session.cultivator(p1), session.cultivator(p2)
        desc = self._narrative(outcome, cult1, cult2, a_intent, b_intent, session.round)
        embed = discord.Embed(
            title=f"⚔️ Round {session.round} · The Clash",
            description=desc,
            color=ui.PURPLE if outcome["kind"] == "counter" else ui.GOLD,
        )
        embed.add_field(
            name=f"{cult1['username']} HP",
            value=f"{session.hp.get(cult1['id'], 0)}/{core_cbt.hp_max(cult1['realm_tier'])}",
            inline=True,
        )
        embed.add_field(
            name=f"{cult2['username']} HP",
            value=f"{session.hp.get(cult2['id'], 0)}/{core_cbt.hp_max(cult2['realm_tier'])}",
            inline=True,
        )
        embed.add_field(
            name="Dao Heart",
            value=f"{session.dao_heart.get(cult1['id'], 0)} · {session.dao_heart.get(cult2['id'], 0)}",
            inline=True,
        )
        try:
            await session.channel.send(embed=embed)
        except Exception:
            pass

    def _narrative(self, outcome: dict, cult1: dict, cult2: dict,
                   a_intent: dict, b_intent: dict, round_no: int) -> str:
        kind = outcome["kind"]
        n1, n2 = cult1["username"], cult2["username"]
        if kind == "mutual_negation":
            return f"{n1} and {n2} meet in a thunderclap of intent — **both blows annihilate each other** in mid-air. Sparks rain. Neither lands."
        if kind == "counter":
            return f"{n2} **reads {n1}'s intent like an open scroll** and counters with devastating precision! {n1} takes {outcome['damage_a']} damage!"
        if kind == "retreat":
            return "One cultivator forfeits the field."
        parts = []
        if outcome["damage_b"] > 0:
            parts.append(f"{n1} lands a blow for **{outcome['damage_b']} damage**.")
        if outcome["damage_a"] > 0:
            parts.append(f"{n2} answers with **{outcome['damage_a']} damage**.")
        if "parried" in outcome.get("notes", []) or "blocked" in outcome.get("notes", []):
            parts.append("The incoming strike is blunted by a careful guard.")
        if "resisted" in outcome.get("notes", []):
            parts.append("Law resonance shaves the blow's edge.")
        if not parts:
            parts.append("Both intents clash and dissipate — a standoff.")
        return " ".join(parts)

    def _check_end(self, session: CombatSession) -> dict | None:
        for uid in session.player_ids():
            cult = session.cultivator(uid)
            if session.hp.get(cult["id"], 0) <= 0:
                return {"defeated_uid": uid, "reason": "defeat"}
            if session.dao_heart.get(cult["id"], 0) <= core_cbt.DAO_HEART_MIN:
                return {"defeated_uid": uid, "reason": "dao_heart"}
        if session.pending.get(session.player_ids()[0]) == "retreat":
            return {"defeated_uid": session.player_ids()[0], "reason": "retreat"}
        if session.pending.get(session.player_ids()[1]) == "retreat":
            return {"defeated_uid": session.player_ids()[1], "reason": "retreat"}
        # Stall guard: a duel that never lands a killing blow ends by HP
        if session.round >= core_cbt.MAX_DUEL_ROUNDS:
            p1, p2 = session.player_ids()
            h1 = session.hp.get(session.cultivator(p1)["id"], 0)
            h2 = session.hp.get(session.cultivator(p2)["id"], 0)
            if h1 == h2:
                return {"draw": True}
            return {"defeated_uid": p1 if h1 < h2 else p2, "reason": "draw"}
        return None

    async def _end_duel(self, duel: DuelSession, defeated_uid: int | None = None,
                        reason: str = "defeat") -> None:
        duel.state = "ended"
        duel.result = {"reason": reason}
        if duel.timer:
            duel.timer.cancel()

        if defeated_uid is None:
            # Draw (stall cap): refund wagers, no titles, log without a loser.
            async with self.bot.db.transaction():
                if duel.wager:
                    ids = (duel.cultivator(duel.p1_uid)["id"], duel.cultivator(duel.p2_uid)["id"])
                    await self.bot.db.execute(
                        "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id IN (?,?)",
                        (duel.wager, *ids),
                    )
                await self.bot.db.execute(
                    "INSERT INTO combat_log (guild_id, winner_id, loser_id, mode, rounds, reason,"
                    " wager_type, wager_amount) VALUES (?,?,NULL,?,?,?,?,?)",
                    (duel.guild_id, "duel", duel.round, reason,
                     "stones" if duel.wager else "none", duel.wager),
                )
            embed = discord.Embed(
                title="🤝 The duel ends in a draw!",
                description=(f"Neither cultivator could claim victory after **{duel.round} rounds**."
                             + ("\nWagers returned to both fighters." if duel.wager else "")),
                color=ui.GOLD,
            )
            try:
                await duel.channel.send(embed=embed)
            except Exception:
                pass
            self.duels.pop(duel.key, None)
            return

        winner_uid = duel.p2_uid if defeated_uid == duel.p1_uid else duel.p1_uid
        winner, loser = duel.cultivator(winner_uid), duel.cultivator(defeated_uid)

        # Titles, Heart Demon, the wager payout, and the combat log land as ONE
        # unit — a crash mid-settle can't pay the winner without recording the
        # fight (or stamp the loser's title and lose the payout).
        async with self.bot.db.transaction():
            # Apply titles + heart demon: a duel loss is a flat +1 Heart Demon Point
            # (internally +0.05 on the 0–1.0 ratio; the player sees the 0–20 scale).
            loser_titles = ui.add_json_title(loser["titles"], "Defeated 败者")
            await self.bot.db.execute(
                "UPDATE cultivators SET titles=?, heart_demon_ratio=MIN(1.0, heart_demon_ratio+0.05), title=? WHERE id=?",
                (loser_titles, "Defeated 败者", loser["id"]),
            )
            winner_titles = ui.add_json_title(winner["titles"], "Victor 胜者")
            await self.bot.db.execute(
                "UPDATE cultivators SET titles=? WHERE id=?", (winner_titles, winner["id"]),
            )
            # Wager payout
            if duel.wager:
                await self.bot.db.execute(
                    "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?",
                    (duel.wager * 2, winner["id"]),
                )
            # Log
            await self.bot.db.execute(
                "INSERT INTO combat_log (guild_id, winner_id, loser_id, mode, rounds, reason, wager_type, wager_amount)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (duel.guild_id, winner["id"], loser["id"], "duel", duel.round, reason,
                 "stones" if duel.wager else "none", duel.wager),
            )
        embed = discord.Embed(
            title=f"🏆 {winner['username']} wins the duel!",
            description=(f"{loser['username']} is defeated ({reason.replace('_', ' ')}).\n"
                         f"Lasted **{duel.round} rounds**.\n"
                         f"{loser['username']} gains **+1 Heart Demon Point** 😈"
                         + (f"\nWager of **{duel.wager * 2:,} 💎** paid to the victor." if duel.wager else "")),
            color=ui.GOLD,
        )
        try:
            await duel.channel.send(embed=embed)
        except Exception:
            pass
        self.duels.pop(duel.key, None)

    # ------------------------------------------------------------- /battle
    @app_commands.command(name="battle", description="Challenge a spirit beast to battle")
    async def battle(self, interaction: discord.Interaction, beast: str) -> None:
        if self._player_in_fight(interaction.user.id):
            await interaction.response.send_message("You are already in a fight!", ephemeral=True)
            return
        beast_data = core_cbt.beast_by_name(beast)
        if not beast_data:
            names = ", ".join(b["name"] for b in core_cbt.SCRIPTED_BEASTS)
            await interaction.response.send_message(f"Unknown beast. Try: {names}", ephemeral=True)
            return
        me = await self._cultivator(interaction.user.id)
        if not me:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return
        key = ("battle", interaction.guild_id, interaction.user.id)
        session = BattleSession(key, interaction.guild_id, interaction.channel, me, beast_data)
        self.battles[key] = session
        embed = discord.Embed(
            title=f"🐾 {beast_data['name']} {beast_data['name_zh']} roars!",
            description=f"Realm {beast_data['realm_tier']} · HP {beast_data['hp']}\n"
                        "It has an **intent pattern** — learn it and counter it. Choose your intent in private DMs!",
            color=ui.CRIMSON,
        )
        await interaction.response.send_message(embed=embed)
        await self._start_round(session)

    async def _resolve_battle_round(self, session: BattleSession) -> None:
        player_value = session.pending.get(session.p_uid, "pass")
        player_cult = session.cultivator(session.p_uid)
        _, pdata = await self._intent_options(player_cult, is_battle=True)
        player_intent = self._build_intent(player_value, player_cult, pdata)
        player_intent["technique_id"] = self._technique_id_of(player_value, pdata)
        await self._spend_intent(session, session.p_uid, player_intent)

        # Beast intent from its pattern (attacks as side B in resolve_round)
        beast_kind = core_cbt.beast_intent_for(session.beast, session.beast_round)
        session.beast_round += 1
        beast_laws = {}  # beasts are lawless in v1
        beast_intent = {
            "kind": "unfold" if beast_kind == "unfold" else "technique",
            "technique": None if beast_kind == "unfold" else {
                "base_damage": 10 + session.beast["realm_tier"] * 3,
                "stored_qi_cost": 0, "law_affinity": None},
            "entries": [], "rank": min(4, max(1, session.beast["realm_tier"] // 3)),
            "law": None if beast_kind != "unfold" else {"name": None, "rank": 2},
            "laws": beast_laws,
            "stats": {"physique": 10 + session.beast["realm_tier"], "spirit": 10 + session.beast["realm_tier"]},
        }

        outcome = core_cbt.resolve_round(player_intent, beast_intent,
                                         random.randint(1, 20), random.randint(1, 20))
        player_dmg = outcome["damage_b"]
        beast_dmg = outcome["damage_a"]
        session.hp[player_cult["id"]] = max(0, session.hp[player_cult["id"]] - player_dmg)
        session.beast_hp = max(0, session.beast_hp - beast_dmg)

        beast = session.beast
        desc = (f"**{beast['name']}** {'unfolds its stance' if beast_kind == 'unfold' else 'strikes'}!\n"
                f"{'You land **%d** damage!' % beast_dmg if beast_dmg else 'Your blow is deflected.'}\n"
                f"{'It wounds you for **%d**.' % player_dmg if player_dmg else ''}")
        embed = discord.Embed(
            title=f"🐾 Round {session.round} vs {beast['name']}",
            description=desc, color=ui.CRIMSON,
        )
        embed.add_field(name="Your HP", value=f"{session.hp[player_cult['id']]}/{core_cbt.hp_max(player_cult['realm_tier'])}", inline=True)
        embed.add_field(name="Beast HP", value=f"{session.beast_hp}/{beast['hp']}", inline=True)
        try:
            await session.channel.send(embed=embed)
        except Exception:
            pass

        if player_intent["kind"] == "retreat":
            await self._end_battle(session, won=False, reason="retreat")
            return
        if session.hp[player_cult["id"]] <= 0 or session.dao_heart[player_cult["id"]] <= core_cbt.DAO_HEART_MIN:
            await self._end_battle(session, won=False, reason="defeat")
            return
        if session.beast_hp <= 0:
            await self._end_battle(session, won=True, reason="victory")
            return
        await self._start_round(session)

    async def _end_battle(self, session: BattleSession, won: bool, reason: str) -> None:
        session.state = "ended"
        if session.timer:
            session.timer.cancel()
        player = session.cultivator(session.p_uid)
        beast = session.beast

        # Rewards (or consequences) + the combat log commit as one unit.
        async with self.bot.db.transaction():
            if won:
                stones = int(beast["stones_reward"])
                titles = ui.add_json_title(player["titles"], f"Beast Slayer 屠兽者")
                await self.bot.db.execute(
                    "UPDATE cultivators SET spirit_stones=spirit_stones+?, titles=? WHERE id=?",
                    (stones, titles, player["id"]),
                )
                learned = await self._grant_random_technique(player["id"])
                extra = f"\nYou mastered **{learned}**!" if learned else ""
                desc = f"You defeated **{beast['name']} {beast['name_zh']}** in {session.round} rounds! +{stones} 💎{extra}"
            else:
                if reason == "retreat":
                    stones = int(beast["stones_reward"] * 0.75)
                    await self.bot.db.execute(
                        "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?",
                        (stones, player["id"]),
                    )
                    desc = f"You retreated from **{beast['name']}** — you salvage {stones} 💎 (75%)."
                else:
                    await self.bot.db.execute(
                        "UPDATE cultivators SET heart_demon_ratio=MIN(1.0, heart_demon_ratio+0.02) WHERE id=?",
                        (player["id"],),
                    )
                    desc = (f"**{beast['name']}** overwhelms you. You flee with your life "
                            f"(Heart Demon **+{gm.heart_demon_delta_str(0.02)} Points**).")
            await self.bot.db.execute(
                "INSERT INTO combat_log (guild_id, winner_id, loser_id, mode, rounds, reason)"
                " VALUES (?,?,?,?,?,?)",
                (session.guild_id, player["id"] if won else None, None if won else player["id"],
                 "battle", session.round, reason),
            )
        embed = discord.Embed(title="🐾 Battle Ended", description=desc, color=ui.GOLD if won else ui.CRIMSON)
        try:
            await session.channel.send(embed=embed)
        except Exception:
            pass
        self.battles.pop(session.key, None)

    async def _grant_random_technique(self, cultivator_id: int) -> str | None:
        learned = await self._learned_techniques(cultivator_id)
        learned_ids = {t["technique_id"] for t in learned}
        rows = await self.bot.db.fetchall(
            "SELECT * FROM techniques WHERE id NOT IN (SELECT technique_id FROM cultivator_techniques WHERE cultivator_id=?) ORDER BY quality",
            (cultivator_id,),
        )
        candidates = [dict(r) for r in rows if r["id"] not in learned_ids]
        if not candidates:
            return None
        choice = random.choice(candidates)
        await self.bot.db.execute(
            "INSERT INTO cultivator_techniques (cultivator_id, technique_id, entries) VALUES (?,?,?)",
            (cultivator_id, choice["id"], json.dumps(core_cbt.roll_entries())),
        )
        return choice["name"]

    # ------------------------------------------------------------- /learn
    @app_commands.command(name="learn", description="Learn a technique by consuming a Technique Scroll")
    async def learn(self, interaction: discord.Interaction, technique_name: str) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return
        tech = await self.bot.db.fetchone(
            "SELECT * FROM techniques WHERE LOWER(name)=LOWER(?)", (technique_name.strip(),)
        )
        if not tech:
            await interaction.response.send_message(f"Technique **{technique_name}** not found in the catalog.", ephemeral=True)
            return
        existing = await self.bot.db.fetchone(
            "SELECT 1 FROM cultivator_techniques WHERE cultivator_id=? AND technique_id=?",
            (me["id"], tech["id"]),
        )
        if existing:
            await interaction.response.send_message("You already know this technique!", ephemeral=True)
            return
        scroll = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND item_type='Technique_Scroll' AND quantity>0 LIMIT 1",
            (me["id"],),
        )
        if not scroll:
            await interaction.response.send_message(
                "You need a **Technique Scroll** to learn from. Earn one from breakthroughs, secret realms, or the auction house.",
                ephemeral=True,
            )
            return
        # Consuming the scroll and granting the technique are one unit — a
        # crash can't eat the scroll and leave you empty-handed.
        async with self.bot.db.transaction():
            if scroll["quantity"] <= 1:
                await self.bot.db.execute("DELETE FROM items WHERE id=?", (scroll["id"],))
            else:
                await self.bot.db.execute("UPDATE items SET quantity=quantity-1 WHERE id=?", (scroll["id"],))
            entries = core_cbt.roll_entries()
            await self.bot.db.execute(
                "INSERT INTO cultivator_techniques (cultivator_id, technique_id, entries) VALUES (?,?,?)",
                (me["id"], tech["id"], json.dumps(entries)),
            )
        q = tech["quality"]
        embed = discord.Embed(
            title=f"📖 Technique Learned: {tech['name']} {tech['name_zh']}",
            description=(f"**{q}** quality technique consumed from a scroll.\n"
                         f"**Entries rolled**: {', '.join(e['name'] for e in core_cbt.ENTRY_POOL if e['key'] in entries) or 'none'}\n"
                         f"*{tech['description']}*"),
            color=ui.GOLD,
        )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- /techniques
    @app_commands.command(name="techniques", description="View your learned techniques, ranks, and entries")
    async def techniques(self, interaction: discord.Interaction) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return
        rows = await self._learned_techniques(me["id"])
        if not rows:
            await interaction.response.send_message("You know no techniques yet. Use `/learn` with a Technique Scroll!", ephemeral=True)
            return
        embed = discord.Embed(title=f"📖 {me['username']}'s Techniques", color=ui.CYAN)
        for t in rows:
            rank = core_cbt.technique_rank(t["mastery_progress"])
            cost = core_cbt.technique_cost(t, rank)
            entries = list(json.loads(t.get("entries") or "[]"))
            entry_str = ", ".join(e["name"] for e in core_cbt.ENTRY_POOL if e["key"] in entries) or "none"
            embed.add_field(
                name=f"{core_cbt.QUALITY_META.get(t['quality'], {}).get('emoji', '')} {t['name']} ({t['name_zh']})",
                value=(f"**{t['quality']}** · Rank {rank} · {cost} SQ · used {t['times_used']}x\n"
                       f"Entries: {entry_str}"),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- /reroll
    @app_commands.command(name="reroll", description="Reroll a technique's entries (1 Comprehension Sand + 100 💎)")
    async def reroll(self, interaction: discord.Interaction, technique_name: str) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return
        tech = await self.bot.db.fetchone(
            "SELECT * FROM techniques WHERE LOWER(name)=LOWER(?)", (technique_name.strip(),)
        )
        if not tech:
            await interaction.response.send_message(f"Technique **{technique_name}** not found.", ephemeral=True)
            return
        reg = await self.bot.db.fetchone(
            "SELECT * FROM cultivator_techniques WHERE cultivator_id=? AND technique_id=?",
            (me["id"], tech["id"]),
        )
        if not reg:
            await interaction.response.send_message("You have not learned this technique.", ephemeral=True)
            return
        if me["spirit_stones"] < 100:
            await interaction.response.send_message("Rerolling costs **100 💎** spirit stones.", ephemeral=True)
            return
        sand = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER('Comprehension Sand') AND quantity>0 LIMIT 1",
            (me["id"],),
        )
        if not sand:
            await interaction.response.send_message("You need **Comprehension Sand** (悟道砂) to reroll entries.", ephemeral=True)
            return
        # Sand, stones, and the rerolled entries commit as one unit.
        async with self.bot.db.transaction():
            if sand["quantity"] <= 1:
                await self.bot.db.execute("DELETE FROM items WHERE id=?", (sand["id"],))
            else:
                await self.bot.db.execute("UPDATE items SET quantity=quantity-1 WHERE id=?", (sand["id"],))
            await self.bot.db.execute(
                "UPDATE cultivators SET spirit_stones=spirit_stones-100 WHERE id=?", (me["id"],)
            )
            entries = core_cbt.roll_entries()
            await self.bot.db.execute(
                "UPDATE cultivator_techniques SET entries=? WHERE cultivator_id=? AND technique_id=?",
                (json.dumps(entries), me["id"], tech["id"]),
            )
        entry_str = ", ".join(e["name"] for e in core_cbt.ENTRY_POOL if e["key"] in entries) or "none"
        embed = discord.Embed(
            title=f"🎲 Entries Rerolled: {tech['name']}",
            description=f"New entries: **{entry_str}**",
            color=ui.GOLD,
        )
        await interaction.response.send_message(embed=embed)
