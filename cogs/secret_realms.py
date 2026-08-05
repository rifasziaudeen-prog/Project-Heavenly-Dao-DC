"""Secret Realms Cog — /realms, /enter_realm, /explore, and /retreat commands."""
from __future__ import annotations

import asyncio
import json
import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import items as core_items, secret_realms as core_sr
from db import queries


class EncounterActionView(discord.ui.View):
    def __init__(self, user_id: int, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.choice = "fight"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This secret realm portal is not yours!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Proceed / Fight · 探索 / 战斗", style=discord.ButtonStyle.primary, custom_id="btn_fight")
    async def fight_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "fight"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Evade / Disarm · 闪避 / 解除", style=discord.ButtonStyle.secondary, custom_id="btn_evade")
    async def evade_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.choice = "evade"
        await interaction.response.defer()
        self.stop()


class SecretRealmsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _cultivator(self, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
        )
        return dict(row) if row else None

    # ================================================================= /realms
    @app_commands.command(
        name="realms",
        description="View available secret realm dungeons and requirements",
    )
    async def realms(self, interaction: discord.Interaction) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        templates = await queries.secret_realm_templates_all(self.bot.db)

        embed = discord.Embed(
            title=ui.format_title("🌌 Secret Realms Directory · 秘境图录", lang),
            description="Ancient mystical realms offering rare materials, technique scrolls, and celestial pills.",
            color=ui.PURPLE,
        )

        for tmpl in templates:
            embed.add_field(
                name=f"{tmpl['name']} (Min Realm: Tier {tmpl['min_realm_tier']})",
                value=(
                    f"*{tmpl['description']}*\n"
                    f"• **Nodes**: {tmpl['node_count']} Encounters | **Entry Cost**: {tmpl['qi_cost']} Qi"
                ),
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================ /enter_realm
    @app_commands.command(
        name="enter_realm",
        description="Open a portal and enter a secret realm dungeon",
    )
    async def enter_realm(
        self,
        interaction: discord.Interaction,
        realm_name: str,
    ) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        # Check for active run
        active_run = await queries.active_realm_run(self.bot.db, row["id"])
        if active_run:
            embed = discord.Embed(
                title=ui.format_title("Active Portal Exists · 秘境探索中", lang),
                description=f"You are already exploring **{active_run['realm_name']}** (Node {active_run['current_node']}/{active_run['max_nodes']})!\nUse `/explore` to continue or `/retreat` to exit.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        tmpl = await queries.secret_realm_template_by_name(self.bot.db, realm_name)
        if not tmpl:
            await interaction.response.send_message(f"Secret Realm **{realm_name}** not found. Check `/realms`.", ephemeral=True)
            return

        can_enter, err_msg = core_sr.can_enter_realm(tmpl, row)
        if not can_enter:
            embed = discord.Embed(
                title=ui.format_title("Portal Sealed · 无法进入", lang),
                description=err_msg,
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Deduct Qi cost
        await self.bot.db.execute(
            "UPDATE cultivators SET qi_current=qi_current-? WHERE id=?",
            (tmpl["qi_cost"], row["id"]),
        )

        # Insert active run
        await self.bot.db.execute(
            "INSERT INTO secret_realm_runs (cultivator_id, realm_name, current_node, max_nodes, status, accumulated_loot)"
            " VALUES (?,?,?,?,'active','[]')",
            (row["id"], tmpl["name"], 1, tmpl["node_count"]),
        )

        embed = discord.Embed(
            title=ui.format_title(f"🌌 Portal Opened: {tmpl['name']}", lang),
            description=(
                f"You step through the swirling rift into **{tmpl['name']}**!\n"
                f"Dungeon Depth: **{tmpl['node_count']} Nodes** | Qi Consumed: **{tmpl['qi_cost']} Qi**\n\n"
                "Use `/explore` to venture into Node 1!"
            ),
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # =============================================================== /explore
    @app_commands.command(
        name="explore",
        description="Explore the next encounter node in your active secret realm",
    )
    async def explore(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        run = await queries.active_realm_run(self.bot.db, row["id"])
        if not run:
            await interaction.response.send_message("You are not currently in an active secret realm. Use `/enter_realm` to start one.", ephemeral=True)
            return

        tmpl = await queries.secret_realm_template_by_name(self.bot.db, run["realm_name"])
        drop_table = core_items.parse_effect_data(tmpl["drop_table_json"]) if tmpl else None

        node_index = run["current_node"]
        total_nodes = run["max_nodes"]

        # Generate node encounter
        encounter = core_sr.generate_node_encounter(row["realm_tier"], node_index, total_nodes)

        enc_embed = discord.Embed(
            title=ui.format_title(f"🔍 {run['realm_name']} — {encounter['title']}", lang),
            description=f"Encounter Difficulty: **{encounter['difficulty']}**\nChoose your action below!",
            color=ui.GOLD,
        )

        view = EncounterActionView(user_id=interaction.user.id, timeout=30.0)
        await interaction.response.send_message(embed=enc_embed, view=view)

        await view.wait()

        # Resolve encounter
        eq_rows = await self.bot.db.fetchall("SELECT * FROM items WHERE owner_id=? AND is_equipped=1", (row["id"],))
        eq_bonuses = core_items.calculate_equipped_bonuses([dict(r) for r in eq_rows])
        stats = {
            "physique": row["physique"] + eq_bonuses["stat_buffs"]["physique"],
            "spirit": row["spirit"] + eq_bonuses["stat_buffs"]["spirit"],
            "luck": row["luck"] + eq_bonuses["stat_buffs"]["luck"],
            "comprehension": row["comprehension"] + eq_bonuses["stat_buffs"]["comprehension"],
        }

        res = core_sr.resolve_encounter(encounter, stats, view.choice, drop_table)

        accumulated_loot = core_items.parse_effect_data(run["accumulated_loot"]) or []
        if res.get("loot"):
            accumulated_loot.append(res["loot"])

        # Deduct Qi loss / apply HD penalty if failed
        if res.get("qi_loss", 0) > 0 or res.get("heart_demon_delta", 0.0) > 0:
            await self.bot.db.execute(
                "UPDATE cultivators SET qi_current=MAX(0, qi_current-?), heart_demon_ratio=MIN(1.0, heart_demon_ratio+?) WHERE id=?",
                (res.get("qi_loss", 0), res.get("heart_demon_delta", 0.0), row["id"]),
            )

        if node_index >= total_nodes:
            # Dungeon completed! Grant all accumulated loot
            for loot in accumulated_loot:
                await core_items.grant_pill(
                    self.bot.db, row["id"], loot["name"], loot.get("grade", "Mortal"),
                    {"type": "stat_buff", "amount": 5}, quantity=loot.get("quantity", 1)
                )

            await self.bot.db.execute(
                "UPDATE secret_realm_runs SET status='completed', accumulated_loot=? WHERE id=?",
                (json.dumps(accumulated_loot), run["id"]),
            )

            loot_names = ", ".join(f"{l['quantity']}x {l['name']}" for l in accumulated_loot) if accumulated_loot else "None"

            res_embed = discord.Embed(
                title=ui.format_title(f"🏆 Secret Realm Conquered! · {run['realm_name']}", lang),
                description=(
                    f"**Final Outcome**: {res['message']}\n\n"
                    f"🎉 You have completed all {total_nodes} nodes!\n"
                    f"**Acquired Rewards**: {loot_names}"
                ),
                color=ui.PURPLE,
            )
            res_embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
            await interaction.channel.send(embed=res_embed)

        else:
            # Advance node
            next_node = node_index + 1
            await self.bot.db.execute(
                "UPDATE secret_realm_runs SET current_node=?, accumulated_loot=? WHERE id=?",
                (next_node, json.dumps(accumulated_loot), run["id"]),
            )

            res_embed = discord.Embed(
                title=ui.format_title(f"⚔ Node {node_index} Resolved", lang),
                description=f"{res['message']}\n\nAdvanced to **Node {next_node}/{total_nodes}**. Use `/explore` to continue!",
                color=ui.CYAN if res["status"] == "success" else ui.CRIMSON,
            )
            res_embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
            await interaction.channel.send(embed=res_embed)

    # =============================================================== /retreat
    @app_commands.command(
        name="retreat",
        description="Retreat safely from your active secret realm run keeping acquired loot",
    )
    async def retreat(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        run = await queries.active_realm_run(self.bot.db, row["id"])
        if not run:
            await interaction.response.send_message("You have no active secret realm run to retreat from.", ephemeral=True)
            return

        accumulated_loot = core_items.parse_effect_data(run["accumulated_loot"]) or []
        for loot in accumulated_loot:
            await core_items.grant_pill(
                self.bot.db, row["id"], loot["name"], loot.get("grade", "Mortal"),
                {"type": "stat_buff", "amount": 5}, quantity=loot.get("quantity", 1)
            )

        await self.bot.db.execute(
            "UPDATE secret_realm_runs SET status='retreated' WHERE id=?",
            (run["id"],),
        )

        loot_names = ", ".join(f"{l['quantity']}x {l['name']}" for l in accumulated_loot) if accumulated_loot else "None"

        embed = discord.Embed(
            title=ui.format_title(f"🚪 Portal Retreat · {run['realm_name']}", lang),
            description=(
                f"You step back through the rift, leaving the secret realm.\n"
                f"**Retained Loot**: {loot_names}"
            ),
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)
