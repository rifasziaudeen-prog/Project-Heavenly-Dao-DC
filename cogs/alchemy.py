"""Alchemy Cog — /recipes, /alchemy_status, and /refine_pill interactive 3-stage mini-game."""
from __future__ import annotations

import asyncio
import json
import random
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import alchemy as core_alchemy, items as core_items
from core import math as gm
from db import queries


# ============================================================================
# Discord Views & Buttons for Mini-Game
# ============================================================================
class FireControlView(discord.ui.View):
    def __init__(self, user_id: int, required_count: int = 3, timeout: float = 10.0) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.required_count = required_count
        self.player_pattern: List[str] = []
        self.finished = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This alchemy flame is not yours to control!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Low Flame", style=discord.ButtonStyle.secondary, custom_id="btn_low")
    async def low_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.player_pattern.append("Low")
        await interaction.response.defer()
        if len(self.player_pattern) >= self.required_count:
            self.stop()

    @discord.ui.button(label="Medium Flame", style=discord.ButtonStyle.primary, custom_id="btn_med")
    async def med_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.player_pattern.append("Medium")
        await interaction.response.defer()
        if len(self.player_pattern) >= self.required_count:
            self.stop()

    @discord.ui.button(label="High Flame", style=discord.ButtonStyle.danger, custom_id="btn_high")
    async def high_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.player_pattern.append("High")
        await interaction.response.defer()
        if len(self.player_pattern) >= self.required_count:
            self.stop()


class IngredientOrderSelect(discord.ui.Select):
    def __init__(self, ingredients: List[str]) -> None:
        options = [
            discord.SelectOption(label=ing, value=ing, description=f"Add {ing} into cauldron")
            for ing in ingredients
        ]
        super().__init__(placeholder="Select ingredient sequence...", min_values=1, max_values=len(ingredients), options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.player_order = list(self.values)
        await interaction.response.defer()
        self.view.stop()


class IngredientOrderView(discord.ui.View):
    def __init__(self, user_id: int, ingredients: List[str], timeout: float = 15.0) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.player_order: List[str] = []
        self.add_item(IngredientOrderSelect(ingredients))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This cauldron is not yours!", ephemeral=True)
            return False
        return True


# ============================================================================
# Alchemy Cog
# ============================================================================
class AlchemyCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _cultivator(self, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
        )
        return dict(row) if row else None

    # =============================================================== /recipes
    @app_commands.command(
        name="recipes",
        description="View pill refinement recipes catalog",
    )
    @app_commands.choices(
        grade=[
            app_commands.Choice(name="Mortal", value="Mortal"),
            app_commands.Choice(name="Earth", value="Earth"),
            app_commands.Choice(name="Heaven", value="Heaven"),
            app_commands.Choice(name="Immortal", value="Immortal"),
            app_commands.Choice(name="God", value="God"),
        ]
    )
    async def recipes(
        self,
        interaction: discord.Interaction,
        grade: app_commands.Choice[str] | None = None,
    ) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        grade_val = grade.value if grade else None
        recipe_rows = await queries.recipes_by_grade(self.bot.db, grade_val)

        if not recipe_rows:
            embed = discord.Embed(
                title=ui.format_title("No Recipes Found · 未找到丹方", lang),
                description="No recipes available for the selected grade filter.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title=ui.format_title("📜 Alchemy Recipe Scroll · 炼丹方册", lang),
            description="Master these ancient formulas to refine pills for power and longevity.",
            color=ui.GOLD,
        )

        for rec in recipe_rows:
            ings = core_items.parse_effect_data(rec["ingredients"])
            if isinstance(ings, list):
                ing_str = ", ".join(f"{i['quantity']}x {i['item_name']}" for i in ings)
            else:
                ing_str = "None"

            eff = core_items.parse_effect_data(rec["effect_on_success"])
            eff_desc = core_items.format_effect_description(eff, lang)
            qi_cost = core_alchemy.calculate_qi_cost(rec["grade"])

            embed.add_field(
                name=f"{rec['name']} ({rec['grade']})",
                value=(
                    f"**Min Realm**: Tier {rec['required_realm_tier']} | **Mastery Req**: {rec['required_alchemy_mastery']}\n"
                    f"**Ingredients**: {ing_str}\n"
                    f"**Base Rate**: {rec['base_success_rate']:.0%} | **Qi Cost**: {qi_cost} Qi\n"
                    f"**Output**: *{eff_desc}*"
                ),
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ======================================================== /alchemy_status
    @app_commands.command(
        name="alchemy_status",
        description="Check your alchemy mastery level, cauldron, and refinement history",
    )
    async def alchemy_status(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        attempts = await queries.alchemy_attempts_by_cultivator(self.bot.db, row["id"], limit=5)

        cauldron_name = row["equipped_cauldron"].title() if row["equipped_cauldron"] != "none" else "None"
        cauldron_bonus = core_alchemy.CAULDRON_BONUS.get(row["equipped_cauldron"].lower(), 0.0)

        embed = discord.Embed(
            title=ui.format_title(f"⚗️ {row['username']}'s Alchemy Status · 炼丹术造诣", lang),
            description=f"Alchemy Mastery Level: **{row['alchemy_mastery']}** (+{row['alchemy_mastery'] * 2}% Success Bonus)",
            color=ui.PURPLE,
        )
        embed.add_field(name="Alchemy Mastery", value=str(row["alchemy_mastery"]), inline=True)
        embed.add_field(name="Alchemy Fame", value=str(row["alchemy_fame"]), inline=True)
        embed.add_field(
            name="Equipped Cauldron",
            value=f"{cauldron_name} (+{cauldron_bonus:.0%} bonus)",
            inline=True,
        )

        if attempts:
            history_lines = []
            for att in attempts:
                tag = "✨ MIRACLE" if att["result"] == "miracle" else ("🎉 SUCCESS" if att["result"] == "success" else ("💥 EXPLOSION" if att["result"] == "explosion" else "❌ FAILURE"))
                history_lines.append(f"• **{att['recipe_name']}** — {tag} ({att['final_rate']:.0%} rate)")
            embed.add_field(name="Recent Refinements", value="\n".join(history_lines), inline=False)
        else:
            embed.add_field(name="Recent Refinements", value="No refinement attempts yet.", inline=False)

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================ /refine_pill
    @app_commands.command(
        name="refine_pill",
        description="Refine a pill through a 3-stage interactive mini-game",
    )
    async def refine_pill(
        self,
        interaction: discord.Interaction,
        recipe_name: str,
    ) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        recipe = await queries.recipe_by_name(self.bot.db, recipe_name)
        if not recipe:
            embed = discord.Embed(
                title=ui.format_title("Recipe Not Found · 丹方不存在", lang),
                description=f"No recipe named **{recipe_name}** exists.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Fetch inventory
        inv_rows = await self.bot.db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND quantity > 0",
            (row["id"],),
        )
        inventory = [dict(r) for r in inv_rows]

        # 1. Validate recipe access
        can_access, err_msg = core_alchemy.validate_recipe_access(
            recipe, row["realm_tier"], row["alchemy_mastery"], inventory
        )
        if not can_access:
            embed = discord.Embed(
                title=ui.format_title("Refinement Cannot Begin · 无法炼制", lang),
                description=err_msg,
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Check Qi cost
        qi_cost = core_alchemy.calculate_qi_cost(recipe["grade"])
        if row["qi_current"] < qi_cost:
            embed = discord.Embed(
                title=ui.format_title("Insufficient Qi · 灵力不足", lang),
                description=f"Refining **{recipe['name']}** requires **{qi_cost} Qi**. You have {row['qi_current']}.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Deduct Qi cost & ingredients
        await self.bot.db.execute(
            "UPDATE cultivators SET qi_current=qi_current-? WHERE id=?",
            (qi_cost, row["id"]),
        )
        ing_list = core_items.parse_effect_data(recipe["ingredients"])
        if isinstance(ing_list, list):
            await core_items.consume_ingredients(self.bot.db, row["id"], ing_list)

        # Deferred ephemeral response to initialize cauldron
        await interaction.response.send_message(
            f"⚗️ Cauldron pre-heated for **{recipe['name']}**! Starting mini-game...",
            ephemeral=True,
        )

        # =========================================================================
        # STAGE 1: Fire Control Rhythm Game
        # =========================================================================
        target_pattern = random.choices(["Low", "Medium", "High"], k=3)
        pattern_str = " -> ".join(target_pattern)

        stage1_embed = discord.Embed(
            title=ui.format_title(f"🔥 Stage 1: Fire Control — {recipe['name']}", lang),
            description=(
                f"Memorize and repeat the flame pattern:\n"
                f"🔥 **[ {pattern_str} ]** 🔥\n\n"
                "Click the buttons below in the exact sequence!"
            ),
            color=ui.GOLD,
        )

        fire_view = FireControlView(user_id=interaction.user.id, required_count=3, timeout=10.0)
        stage1_msg = await interaction.channel.send(embed=stage1_embed, view=fire_view)

        await fire_view.wait()
        fire_score = core_alchemy.score_fire_control(fire_view.player_pattern, target_pattern)

        # Disable buttons
        for child in fire_view.children:
            child.disabled = True
        await stage1_msg.edit(embed=stage1_embed, view=fire_view)

        # =========================================================================
        # STAGE 2: Ingredient Order
        # =========================================================================
        correct_order = [ing["item_name"] for ing in ing_list] if isinstance(ing_list, list) else ["Herb"]
        shuffled_ingredients = list(correct_order)
        random.shuffle(shuffled_ingredients)

        stage2_embed = discord.Embed(
            title=ui.format_title(f"🌿 Stage 2: Ingredient Sequence — {recipe['name']}", lang),
            description=(
                f"Fire Control Score: **{fire_score}/10**\n\n"
                "Select the ingredients to add to the cauldron:"
            ),
            color=ui.CYAN,
        )

        ing_view = IngredientOrderView(user_id=interaction.user.id, ingredients=shuffled_ingredients, timeout=12.0)
        stage2_msg = await interaction.channel.send(embed=stage2_embed, view=ing_view)

        await ing_view.wait()
        ing_score = core_alchemy.score_ingredient_order(ing_view.player_order, correct_order)

        for child in ing_view.children:
            child.disabled = True
        await stage2_msg.edit(embed=stage2_embed, view=ing_view)

        # =========================================================================
        # STAGE 3: Spiritual Sense Check
        # =========================================================================
        sense_score = core_alchemy.score_spiritual_sense(row["comprehension"], recipe["recipe_difficulty"])

        # =========================================================================
        # FINAL RESOLUTION
        # =========================================================================
        final_rate = core_alchemy.calculate_success_rate(
            recipe["base_success_rate"],
            row["alchemy_mastery"],
            row["equipped_cauldron"],
            fire_score,
            ing_score,
            sense_score,
        )

        res_type = core_alchemy.roll_result(final_rate)

        # +1 Alchemy Mastery per attempt
        await self.bot.db.execute(
            "UPDATE cultivators SET alchemy_mastery=alchemy_mastery+1, alchemy_fame=alchemy_fame+? WHERE id=?",
            (1 if res_type in (core_alchemy.AlchemyResult.SUCCESS, core_alchemy.AlchemyResult.MIRACLE) else 0, row["id"]),
        )

        # Log attempt
        await self.bot.db.execute(
            "INSERT INTO alchemy_attempts (cultivator_id, recipe_name, result, final_rate, fire_score, ingredient_score, sense_score)"
            " VALUES (?,?,?,?,?,?,?)",
            (row["id"], recipe["name"], res_type.value, final_rate, fire_score, ing_score, sense_score),
        )

        # Outcome Embed
        res_embed = discord.Embed(color=ui.GOLD)
        res_embed.add_field(
            name="Mini-Game Scores",
            value=f"🔥 Fire: **{fire_score}/10** | 🌿 Ingredients: **{ing_score}/10** | ✨ Sense: **{sense_score}/10**",
            inline=False,
        )
        res_embed.add_field(name="Final Success Rate", value=f"**{final_rate:.0%}**", inline=False)

        if res_type == core_alchemy.AlchemyResult.MIRACLE:
            res_embed.title = "✨ MIRACLE REFINEMENT · 天降祥瑞"
            eff_raw = core_items.parse_effect_data(recipe["effect_on_success"])
            eff = core_alchemy.resolve_success_effect(eff_raw, miracle=True)
            await core_items.grant_pill(self.bot.db, row["id"], recipe["result_pill_name"], recipe["grade"], eff, quantity=1)

            eff_desc = core_items.format_effect_description(eff, lang)
            res_embed.description = (
                f"The heavens smile upon you! Refined **1x {recipe['result_pill_name']} ({recipe['grade']})** with **1.5x Miracle Boost**!\n"
                f"Effect: *{eff_desc}*"
            )
            res_embed.color = ui.PURPLE

        elif res_type == core_alchemy.AlchemyResult.SUCCESS:
            res_embed.title = "🎉 REFINEMENT SUCCESS · 炼丹成功"
            eff_raw = core_items.parse_effect_data(recipe["effect_on_success"])
            await core_items.grant_pill(self.bot.db, row["id"], recipe["result_pill_name"], recipe["grade"], eff_raw, quantity=1)

            eff_desc = core_items.format_effect_description(eff_raw, lang)
            res_embed.description = (
                f"Successfully refined **1x {recipe['result_pill_name']} ({recipe['grade']})**!\n"
                f"Effect: *{eff_desc}*"
            )
            res_embed.color = ui.GOLD

        elif res_type == core_alchemy.AlchemyResult.EXPLOSION:
            res_embed.title = "💥 CAULDRON EXPLOSION · 炸炉"
            # Deduct 25% Qi and +1 Heart Demon Point (0.05 ratio)
            qi_loss = int(row["qi_current"] * 0.25)
            await self.bot.db.execute(
                "UPDATE cultivators SET qi_current=MAX(0, qi_current-?), heart_demon_ratio=MIN(1.0, heart_demon_ratio+0.05) WHERE id=?",
                (qi_loss, row["id"]),
            )
            res_embed.description = (
                "The violent flames erupt! The cauldron shatters into ash!\n"
                f"Lost **{ui.format_qi(qi_loss, lang)}** and gained "
                f"**{gm.heart_demon_delta_str(0.05)} Heart Demon Points**."
            )
            res_embed.color = ui.CRIMSON

        else:  # FAILURE
            res_embed.title = "🌫️ REFINEMENT FAILED · 炼制失败"
            await self.bot.db.execute(
                "UPDATE cultivators SET heart_demon_ratio=MIN(1.0, heart_demon_ratio+0.01) WHERE id=?",
                (row["id"],),
            )
            res_embed.description = (
                "The medicinal essence burns to dark dross. Refinement failed.\n"
                f"Gained **{gm.heart_demon_delta_str(0.01)} Heart Demon Points** from frustration."
            )
            res_embed.color = ui.OBSIDIAN

        res_embed.set_footer(text=f"+1 Alchemy Mastery gained! · {ui.format_title('Heavenly Dao Engine · 天道引擎', lang)}")
        await interaction.channel.send(embed=res_embed)
