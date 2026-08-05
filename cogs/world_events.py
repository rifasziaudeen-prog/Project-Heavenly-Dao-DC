"""World Events Cog — /events, /event_join, /event_attack, /event_status, /event_claim, and /spawn_event.

Since v1.11.0 /event_attack is World-boss Contendance: the boss telegraphs a
scripted intent pattern and each attacker resolves one exchange with the
shared combat engine (Stored Qi cost, law counters, parries, HP stakes).
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import combat as core_cbt
from core import dao_laws as core_dl
from core import items as core_items
from core import math as gm
from core import world_events as core_we
from db import queries


class WorldEventsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _cultivator(self, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
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
        row = await self._cultivator(interaction.user.id)
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
            "INSERT INTO world_event_participants"
            " (event_id, cultivator_id, sect_id, damage_dealt, hp_current)"
            " VALUES (?,?,?,0,?)",
            (event_id, row["id"], row["sect_id"], core_cbt.hp_max(row["realm_tier"])),
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
        description="Fight the World Boss: counter its intent with your own (costs Stored Qi)",
    )
    @app_commands.choices(choice=[
        app_commands.Choice(name="⚔️ Technique", value="technique"),
        app_commands.Choice(name="☯️ Unfold Law", value="unfold"),
        app_commands.Choice(name="🗡️ Artifact Parry", value="artifact"),
        app_commands.Choice(name="💊 Pill", value="pill"),
        app_commands.Choice(name="🏳️ Retreat", value="retreat"),
    ])
    async def event_attack(
        self, interaction: discord.Interaction, event_id: int,
        choice: app_commands.Choice[str],
    ) -> None:
        row = await self._cultivator(interaction.user.id)
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

        now = datetime.now(timezone.utc)

        # --- Defeat cooldown gate: overwhelmed cultivators must recover.
        hp = part.get("hp_current")
        hp = int(hp) if hp is not None else core_cbt.hp_max(row["realm_tier"])
        last_attack = part.get("last_attack_at")
        if hp <= 0 and last_attack:
            try:
                defeated_at = datetime.fromisoformat(last_attack)
                if defeated_at.tzinfo is None:
                    defeated_at = defeated_at.replace(tzinfo=timezone.utc)
                elapsed = now - defeated_at
                if elapsed < timedelta(minutes=core_we.BOSS_DEFEAT_COOLDOWN):
                    left = core_we.BOSS_DEFEAT_COOLDOWN - int(elapsed.total_seconds() // 60)
                    await interaction.response.send_message(
                        f"You were overwhelmed by the World Boss! Recover for **{left} more minutes** "
                        "before re-engaging.", ephemeral=True)
                    return
            except ValueError:
                pass
            hp = core_cbt.hp_max(row["realm_tier"])  # recovered — back to full
        elif last_attack:
            # Flat HP recovery over time between attacks (no percentages).
            try:
                last_dt = datetime.fromisoformat(last_attack)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                hours = (now - last_dt).total_seconds() / 3600.0
                if hours > 0:
                    hp = min(core_cbt.hp_max(row["realm_tier"]),
                             hp + int(hours * core_we.BOSS_HP_REGEN_PER_HOUR))
            except ValueError:
                pass

        # --- Build the intent + its Stored Qi cost.
        round_index = int(part.get("boss_round") or 0)
        boss_unfold = core_we.boss_intent_for(evt["event_type"], round_index) == "unfold"
        intent, cost, err = await self._build_player_intent(row, choice.value, boss_unfold=boss_unfold)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if cost > 0 and int(row["stored_qi_current"] or 0) < cost:
            await interaction.response.send_message(
                f"You need **{cost} Stored Qi** for **{choice.name}** — you have "
                f"**{int(row['stored_qi_current'] or 0):,}**. Use a Stored Qi pill "
                "(`/use Stored Qi Elixir`) or wait for passive regen.", ephemeral=True)
            return

        # --- Spend the round.
        if cost > 0:
            await self.bot.db.execute(
                "UPDATE cultivators SET stored_qi_current=MAX(0, stored_qi_current-?) WHERE id=?",
                (cost, row["id"]),
            )
        restored_qi = 0
        if intent["kind"] == "pill":
            restored_qi = await self._consume_stored_qi_pill(row)
            hp = min(core_cbt.hp_max(row["realm_tier"]), hp + core_we.BOSS_PILL_HEAL)
        if intent["kind"] == "technique" and intent.get("technique_id"):
            await self.bot.db.execute(
                "UPDATE cultivator_techniques SET mastery_progress=MIN(100.0, mastery_progress+?),"
                " times_used=times_used+1 WHERE cultivator_id=? AND technique_id=?",
                (core_cbt.TECHNIQUE_MASTERY_PER_USE, row["id"], intent["technique_id"]),
            )

        # --- Resolve the exchange (boss side A, player side B).
        phase = int(evt["current_phase"] or 1)
        res = core_we.resolve_boss_exchange(
            intent, evt["event_type"], phase, round_index,
            d20_player=random.randint(1, 20), d20_boss=random.randint(1, 20),
        )

        hp = max(0, hp - res["damage_to_player"])
        new_boss_hp = max(0, int(evt["boss_hp_current"]) - res["damage_to_boss"])
        new_phase, phase_narrative = core_we.determine_boss_phase(new_boss_hp, evt["boss_hp_max"])
        new_status = "completed" if new_boss_hp <= 0 else "active"

        # --- Persist participant state.
        await self.bot.db.execute(
            "UPDATE world_event_participants SET damage_dealt=damage_dealt+?,"
            " hp_current=?, last_attack_at=?, boss_round=boss_round+1"
            " WHERE event_id=? AND cultivator_id=?",
            (res["damage_to_boss"], hp, now.isoformat(), event_id, row["id"]),
        )
        await self.bot.db.execute(
            "UPDATE world_events SET boss_hp_current=?, current_phase=?, narrative_state=?, status=? WHERE id=?",
            (new_boss_hp, new_phase, phase_narrative, new_status, event_id),
        )

        # --- Defeat: no death, but +1 Heart Demon Point and a recovery window.
        if hp <= 0:
            await self.bot.db.execute(
                "UPDATE cultivators SET heart_demon_ratio=MIN(1.0, heart_demon_ratio+?) WHERE id=?",
                (core_we.BOSS_DEFEAT_HD_RATIO, row["id"]),
            )
            embed = discord.Embed(
                title=ui.format_title("💀 Overwhelmed · 力竭败退", lang),
                description=(
                    f"The World Boss's assault shatters your guard — you collapse on the battlefield "
                    f"and are dragged to safety. No death, but your Dao heart is scarred: "
                    f"**+1 Heart Demon Point** 😈.\n"
                    f"You recover in **{core_we.BOSS_DEFEAT_COOLDOWN} minutes**."
                ),
                color=ui.CRIMSON,
            )
            embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
            await interaction.response.send_message(embed=embed)
            return

        # --- Success / partial round embed.
        stance = core_we.boss_stance_label(evt["event_type"], round_index, lang)
        notes = self._round_notes(res, intent)
        desc_lines = [
            f"The boss {stance}…",
            notes,
            f"**Boss HP**: {new_boss_hp:,} / {evt['boss_hp_max']:,}",
        ]
        if restored_qi:
            desc_lines.append(f"💊 Restored **+{restored_qi} Stored Qi** (heal +{core_we.BOSS_PILL_HEAL} HP).")
        embed = discord.Embed(
            title=ui.format_title(f"💥 Round {round_index + 1} · The Clash · 灵威交锋", lang),
            description="\n".join(desc_lines),
            color=ui.PURPLE if res["kind"] == "counter" else ui.GOLD,
        )
        embed.add_field(
            name="Your HP",
            value=f"{hp:,} / {core_cbt.hp_max(row['realm_tier']):,}",
            inline=True,
        )
        sq_eff_max = gm.stored_qi_effective_max(row["stored_qi_max"], row["stored_qi_max_bonus"])
        sq_display = min(sq_eff_max, int(row["stored_qi_current"] or 0) - cost + restored_qi)
        embed.add_field(
            name="Stored Qi",
            value=f"{sq_display:,} / {sq_eff_max:,}",
            inline=True,
        )
        embed.add_field(name="Phase", value=f"{new_phase}/5", inline=True)
        if new_boss_hp <= 0:
            embed.title = ui.format_title("🏆 WORLD BOSS SLAIN! · 天劫终结", lang)
            embed.description = (f"**{row['username']}** delivered the final strike! "
                                 f"The World Boss has been vanquished!\n"
                                 f"Use `/event_claim {event_id}` to receive your ranking rewards.")
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------- world-boss helpers
    def _round_notes(self, res: dict, intent: dict) -> str:
        """Narrate the exchange outcome."""
        kind = res["kind"]
        dmg = res["damage_to_boss"]
        taken = res["damage_to_player"]
        intent_label = {
            "technique": "⚔️ your technique", "unfold": "☯️ your law unfold",
            "artifact": "🗡️ your artifact guard", "pill": "💊 your pill",
            "retreat": "🏳️ your retreat",
        }.get(intent["kind"], "your intent")
        if kind == "counter":
            return (f"☯️ **COUNTER!** Your law reads the Sword Intent like an open scroll — "
                    f"the boss takes **{dmg:,} damage** and reels, landing nothing!")
        if kind == "mutual_negation":
            return (f"Your clash meets the boss's power head-on — both blows annihilate "
                    f"each other in mid-air.")
        if kind == "retreat":
            return "You slip back from the battlefield, unharmed."
        parts = []
        if dmg:
            parts.append(f"You land **{dmg:,} damage** on the boss with {intent_label}!")
        if taken:
            parts.append(f"Its counterblow wounds you for **{taken:,} HP**.")
        if "parried" in res.get("notes", []) or "blocked" in res.get("notes", []):
            parts.append("The incoming strike is blunted by your guard.")
        if not parts:
            parts.append("The boss's stance holds; your blow finds no purchase.")
        return " ".join(parts)

    async def _best_technique(self, cultivator_id: int) -> dict | None:
        rows = await self.bot.db.fetchall(
            "SELECT ct.*, t.name, t.base_damage, t.stored_qi_cost, t.law_affinity, t.quality"
            " FROM cultivator_techniques ct JOIN techniques t ON t.id=ct.technique_id"
            " WHERE ct.cultivator_id=? ORDER BY ct.mastery_progress DESC LIMIT 1",
            (cultivator_id,),
        )
        return dict(rows[0]) if rows else None

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
        return min(core_cbt.ARTIFACT_PARRY_CAP, core_cbt.ARTIFACT_PARRY_BASE + bonus)

    async def _build_player_intent(
        self, row: dict, choice: str, boss_unfold: bool = False
    ) -> tuple[dict | None, int, str | None]:
        """Return (intent, stored_qi_cost, error_message) for the round choice."""
        stats = {"physique": int(row.get("physique", 10)), "spirit": int(row.get("spirit", 10))}
        laws = await self._law_ranks(row["id"])
        base = {"stats": stats, "laws": laws}

        if choice == "technique":
            t = await self._best_technique(row["id"])
            if t:
                intent = {
                    **base, "kind": "technique",
                    "technique": {"base_damage": t["base_damage"],
                                  "stored_qi_cost": t["stored_qi_cost"],
                                  "law_affinity": t["law_affinity"]},
                    "entries": list(json.loads(t.get("entries") or "[]")),
                    "rank": core_cbt.technique_rank(t["mastery_progress"]),
                    "technique_id": t["technique_id"],
                }
                # Match the duel's costing: entry effects (e.g. Overcharge)
                # double the Stored Qi cost too.
                mods = core_cbt.entry_modifiers(intent["entries"])
                cost = int(core_cbt.technique_cost(
                    {"stored_qi_cost": t["stored_qi_cost"]}, intent["rank"]) * mods["cost_mult"])
                return intent, cost, None
            return {**base, "kind": "technique",
                    "technique": {"base_damage": 8, "stored_qi_cost": 5, "law_affinity": None},
                    "entries": [], "rank": 1}, 5, None

        if choice == "unfold":
            # On an unfold round, prefer Law of Sword when owned 2+ ranks ahead
            # so the documented counter is a real choice, not luck of mastery.
            if boss_unfold:
                sw_mastery = laws.get(core_we.BOSS_UNFOLD_LAW, 0.0)
                if core_dl.law_rank(sw_mastery) >= 2:
                    name, mastery = core_we.BOSS_UNFOLD_LAW, sw_mastery
                else:
                    best = max(laws.items(), key=lambda kv: kv[1]) if laws else None
                    name, mastery = best if best else (None, 0.0)
            else:
                best = max(laws.items(), key=lambda kv: kv[1]) if laws else None
                name, mastery = best if best else (None, 0.0)
            if not name or core_dl.law_rank(mastery) < 1:
                return None, 0, "You have no Dao Law unfolded to counter with. " \
                                 "Comprehend one first (`/comprehend`)."
            return {
                **base, "kind": "unfold",
                "law": {"name": name, "rank": core_dl.law_rank(mastery), "mastery": mastery},
            }, core_cbt.LAW_UNFOLD_COST, None

        if choice == "artifact":
            return {**base, "kind": "artifact", "parry": await self._parry_value(row["id"])},\
                core_cbt.ARTIFACT_COST, None

        if choice == "pill":
            has_pill = await self.bot.db.fetchone(
                "SELECT id FROM items WHERE owner_id=? AND quantity>0 AND"
                " effect_data LIKE '%stored_qi_restore%' LIMIT 1", (row["id"],),
            )
            if not has_pill:
                return None, 0, "You carry no Stored Qi pill to consume. Alchemise or buy one first."
            return {**base, "kind": "pill"}, 0, None

        if choice == "retreat":
            return {**base, "kind": "retreat"}, 0, None

        return None, 0, "Unknown intent."

    async def _consume_stored_qi_pill(self, row: dict) -> int:
        """Consume one Stored Qi pill from inventory; returns Stored Qi restored."""
        found = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND quantity>0 AND"
            " effect_data LIKE '%stored_qi_restore%' ORDER BY id LIMIT 1",
            (row["id"],),
        )
        if not found:
            return 0
        eff = core_items.parse_effect_data(found["effect_data"])
        amount = int(eff.get("amount", 0))
        if int(found["quantity"]) <= 1:
            await self.bot.db.execute("DELETE FROM items WHERE id=?", (found["id"],))
        else:
            await self.bot.db.execute(
                "UPDATE items SET quantity=quantity-1 WHERE id=?", (found["id"],))
        await self.bot.db.execute(
            "UPDATE cultivators SET stored_qi_current="
            " MIN(stored_qi_max+stored_qi_max_bonus, stored_qi_current+?) WHERE id=?",
            (amount, row["id"]),
        )
        return amount

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

        # Your battlefield state + the boss's telegraphed stance for your round.
        me = await self._cultivator(interaction.user.id)
        if me:
            my_part = await queries.event_participant(self.bot.db, event_id, me["id"])
            if my_part:
                round_index = int(my_part.get("boss_round") or 0)
                stance = core_we.boss_stance_label(evt["event_type"], round_index, lang)
                hp = my_part.get("hp_current")
                hp = int(hp) if hp is not None else core_cbt.hp_max(me["realm_tier"])
                mine = (
                    f"The boss **{stance}**.\n"
                    f"Your HP: **{hp:,}** / {core_cbt.hp_max(me['realm_tier']):,} · "
                    f"Your round: **{round_index + 1}**"
                )
                if hp <= 0 and my_part.get("last_attack_at"):
                    try:
                        defeated_at = datetime.fromisoformat(my_part["last_attack_at"])
                        if defeated_at.tzinfo is None:
                            defeated_at = defeated_at.replace(tzinfo=timezone.utc)
                        elapsed = datetime.now(timezone.utc) - defeated_at
                        if elapsed < timedelta(minutes=core_we.BOSS_DEFEAT_COOLDOWN):
                            left = core_we.BOSS_DEFEAT_COOLDOWN - int(elapsed.total_seconds() // 60)
                            mine += f"\n💀 Recovering from defeat — **{left} min** left."
                    except ValueError:
                        pass
                embed.add_field(name="Your Battlefield", value=mine, inline=False)

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
        row = await self._cultivator(interaction.user.id)
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

        row = await self._cultivator(interaction.user.id)
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
