"""Items cog — /inventory, /equip, /use, /give, and /item_info slash commands."""
from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import items as core_items
from core import math as gm
from db.queries import get_or_create_cultivator


class ItemsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------ helpers
    async def _cultivator(self, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (user_id,)
        )
        return dict(row) if row else None

    # ============================================================== /inventory
    @app_commands.command(
        name="inventory",
        description="View your inventory of pills, weapons, scrolls, and artifacts",
    )
    async def inventory(
        self,
        interaction: discord.Interaction,
        page: int = 1,
    ) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            embed = discord.Embed(
                title="Unawakened · 未觉醒",
                description="You must `/register` before opening your storage spatial ring.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        items_rows = await self.bot.db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND quantity > 0 ORDER BY is_equipped DESC, grade DESC, name ASC",
            (row["id"],),
        )

        if not items_rows:
            embed = discord.Embed(
                title=ui.format_title("Spatial Ring Empty · 储物戒空无一物", lang),
                description=(
                    "Your spatial storage ring is empty.\n"
                    "Earn items from `/breakthrough` tribulations, daily `/cultivate` streaks, or sect rewards."
                ),
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed)
            return

        # Pagination (8 items per page)
        per_page = 8
        total_items = len(items_rows)
        total_pages = max(1, (total_items + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        paged_items = items_rows[start : start + per_page]

        embed = discord.Embed(
            title=ui.format_title(f"🎒 {row['username']}'s Spatial Ring · 储物袋", lang),
            description=f"Page **{page}/{total_pages}** · Total Items: **{total_items}**",
            color=ui.GOLD,
        )

        for item in paged_items:
            eq_tag = " [Equipped ⚔️]" if item["is_equipped"] else ""
            eff = core_items.parse_effect_data(item["effect_data"])
            eff_desc = core_items.format_effect_description(eff, lang)
            qty_str = f" x{item['quantity']}" if item['quantity'] > 1 else ""

            embed.add_field(
                name=f"{item['name']}{qty_str}{eq_tag}",
                value=f"**Type**: {item['item_type']} | **Grade**: {item['grade']}\n*{eff_desc}*",
                inline=False,
            )

        embed.set_footer(
            text=f"Use /equip or /use <item_name> · {ui.format_title('Heavenly Dao Engine · 天道引擎', lang)}"
        )
        await interaction.response.send_message(embed=embed)

    # ================================================================== /equip
    @app_commands.command(
        name="equip",
        description="Equip or unequip a weapon or technique scroll",
    )
    async def equip(
        self,
        interaction: discord.Interaction,
        item_name: str,
    ) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        target = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) AND quantity > 0",
            (row["id"], item_name.strip()),
        )
        if not target:
            embed = discord.Embed(
                title=ui.format_title("Item Not Found · 未找到物品", lang),
                description=f"You do not own **{item_name}**.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        target_dict = dict(target)
        all_equipped = await self.bot.db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND is_equipped=1",
            (row["id"],),
        )
        equipped_dicts = [dict(r) for r in all_equipped]

        success, msg, to_equip, to_unequip = core_items.equip_toggle(equipped_dicts, target_dict)

        if not success:
            embed = discord.Embed(
                title=ui.format_title("Equip Failed · 装备失败", lang),
                description=msg,
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Perform DB updates
        for uid in to_unequip:
            await self.bot.db.execute(
                "UPDATE items SET is_equipped=0, equipped_slot=NULL WHERE id=?",
                (uid,),
            )
        for eid in to_equip:
            slot = target_dict.get("item_type")
            await self.bot.db.execute(
                "UPDATE items SET is_equipped=1, equipped_slot=? WHERE id=?",
                (slot, eid),
            )

        embed = discord.Embed(
            title=ui.format_title("Equipment Updated · 装备调整", lang),
            description=msg,
            color=ui.GOLD,
        )
        await interaction.response.send_message(embed=embed)

    # ==================================================================== /use
    @app_commands.command(
        name="use",
        description="Consume a pill, talisman, or artifact from your spatial ring",
    )
    async def use(
        self,
        interaction: discord.Interaction,
        item_name: str,
    ) -> None:
        row = await self._cultivator(interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        target = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) AND quantity > 0",
            (row["id"], item_name.strip()),
        )
        if not target:
            embed = discord.Embed(
                title=ui.format_title("Item Not Found · 未找到物品", lang),
                description=f"You do not own **{item_name}**.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        item = dict(target)
        eff = core_items.parse_effect_data(item["effect_data"])
        etype = eff.get("type")

        if item["item_type"] in ("Weapon", "Technique_Scroll"):
            await interaction.response.send_message(
                f"**{item['name']}** is equipment! Use `/equip {item['name']}` instead.",
                ephemeral=True,
            )
            return

        result_msg = f"Consumed **{item['name']}**."

        # Apply effect logic
        if etype == "qi_boost":
            amount = eff.get("amount", 0)
            await self.bot.db.execute(
                "UPDATE cultivators SET qi_current = MIN(qi_capacity, qi_current + ?) WHERE id=?",
                (amount, row["id"]),
            )
            result_msg += f" Gained **+{ui.format_qi(amount, lang)}** into your Dantian."

        elif etype == "heart_demon_purge":
            amount = eff.get("amount", 0.0)
            await self.bot.db.execute(
                "UPDATE cultivators SET heart_demon_ratio = MAX(0.0, heart_demon_ratio - ?) WHERE id=?",
                (amount, row["id"]),
            )
            result_msg += f" Purged **{amount * gm.HD_POINTS_MAX:g} Heart Demon Points**."

        elif etype == "protection":
            ctype = eff.get("charm_type", "karmic_shield")
            await self.bot.db.execute(
                "INSERT INTO dao_protection_charms (owner_id, charm_type, protection_level) VALUES (?, ?, 1)",
                (row["id"], ctype),
            )
            result_msg += f" Absorbed protective charm **{ctype.replace('_', ' ').title()}**!"

        elif etype == "stored_qi_restore":
            amount = eff.get("amount", 0)
            await self.bot.db.execute(
                "UPDATE cultivators SET stored_qi_current ="
                " MIN(stored_qi_max + stored_qi_max_bonus, stored_qi_current + ?) WHERE id=?",
                (amount, row["id"]),
            )
            result_msg += f" Restored **+{amount} Stored Qi (存灵气)**!"

        # Consume 1 quantity
        if item["quantity"] <= 1:
            await self.bot.db.execute("DELETE FROM items WHERE id=?", (item["id"],))
        else:
            await self.bot.db.execute("UPDATE items SET quantity=quantity-1 WHERE id=?", (item["id"],))

        embed = discord.Embed(
            title=ui.format_title("Item Consumed · 物品使用", lang),
            description=result_msg,
            color=ui.GOLD,
        )
        await interaction.response.send_message(embed=embed)

    # =================================================================== /give
    @app_commands.command(
        name="give",
        description="Transfer items to another cultivator in your server",
    )
    async def give(
        self,
        interaction: discord.Interaction,
        recipient: discord.Member,
        item_name: str,
        quantity: int = 1,
    ) -> None:
        if recipient.id == interaction.user.id:
            await interaction.response.send_message("You cannot give items to yourself.", ephemeral=True)
            return
        if quantity < 1:
            await interaction.response.send_message("Quantity must be at least 1.", ephemeral=True)
            return

        sender_row = await self._cultivator(interaction.user.id)
        if not sender_row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        target_row, _ = await get_or_create_cultivator(
            self.bot.db, recipient.id, recipient.display_name, interaction.guild_id
        )

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        sender_item = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) AND quantity>=?",
            (sender_row["id"], item_name.strip(), quantity),
        )
        if not sender_item:
            embed = discord.Embed(
                title=ui.format_title("Trade Failed · 赠送失败", lang),
                description=f"You do not possess **{quantity}x {item_name}**.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        item = dict(sender_item)
        if item["is_equipped"]:
            await interaction.response.send_message(
                f"Unequip **{item['name']}** with `/equip` before trading.",
                ephemeral=True,
            )
            return

        # Subtract from sender
        if item["quantity"] <= quantity:
            await self.bot.db.execute("DELETE FROM items WHERE id=?", (item["id"],))
        else:
            await self.bot.db.execute("UPDATE items SET quantity=quantity-? WHERE id=?", (quantity, item["id"]))

        # Add to recipient (stack if exists)
        recip_item = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) AND is_equipped=0",
            (target_row["id"], item["name"].lower()),
        )
        if recip_item:
            await self.bot.db.execute(
                "UPDATE items SET quantity=quantity+? WHERE id=?",
                (quantity, recip_item["id"]),
            )
        else:
            await self.bot.db.execute(
                "INSERT INTO items (owner_id, name, item_type, grade, effect_data, quantity) VALUES (?,?,?,?,?,?)",
                (target_row["id"], item["name"], item["item_type"], item["grade"], item["effect_data"], quantity),
            )

        embed = discord.Embed(
            title=ui.format_title("🎁 Item Gifted · 赠送完成", lang),
            description=f"{interaction.user.mention} gave **{quantity}x {item['name']}** to {recipient.mention}.",
            color=ui.GOLD,
        )
        await interaction.response.send_message(embed=embed)

    # ============================================================== /item_info
    @app_commands.command(
        name="item_info",
        description="Inspect item details, grade, lore, and parsed effects",
    )
    async def item_info(
        self,
        interaction: discord.Interaction,
        item_name: str,
    ) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        # Search catalog template first, then player inventory
        template = await self.bot.db.fetchone(
            "SELECT * FROM item_templates WHERE LOWER(name)=LOWER(?)",
            (item_name.strip(),),
        )
        if not template:
            row = await self._cultivator(interaction.user.id)
            if row:
                template = await self.bot.db.fetchone(
                    "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?)",
                    (row["id"], item_name.strip()),
                )

        if not template:
            embed = discord.Embed(
                title=ui.format_title("Unknown Item · 未知物品", lang),
                description=f"No artifact named **{item_name}** exists in records.",
                color=ui.CRIMSON,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        item = dict(template)
        eff = core_items.parse_effect_data(item["effect_data"])
        eff_desc = core_items.format_effect_description(eff, lang)

        embed = discord.Embed(
            title=f"🗡️ {item['name']} ({item['grade']})",
            description=item.get("description") or f"A Xianxia artifact of grade **{item['grade']}**.",
            color=ui.GOLD,
        )
        embed.add_field(name="Item Type", value=item["item_type"], inline=True)
        embed.add_field(name="Grade", value=item["grade"], inline=True)
        embed.add_field(name="Effect", value=eff_desc, inline=False)

        await interaction.response.send_message(embed=embed)

    # ==================================================== /recharge_artifact
    @app_commands.command(
        name="recharge_artifact",
        description="Convert spirit stones into energy for your weapon's active ability",
    )
    async def recharge_artifact(
        self, interaction: discord.Interaction, energy: int = 0
    ) -> None:
        me = await self._cultivator(interaction.user.id)
        if not me:
            await interaction.response.send_message(
                "Please `/register` first.", ephemeral=True)
            return

        rows = await self.bot.db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND is_equipped=1 AND item_type='Weapon'"
            " ORDER BY grade DESC",
            (me["id"],),
        )
        target = None
        for r in rows:
            row = dict(r)
            if core_items.parse_active_ability(row.get("effect_data") or "{}"):
                target = row
                break
        if not target:
            await interaction.response.send_message(
                "You have no equipped weapon with an active ability to recharge.",
                ephemeral=True,
            )
            return

        max_energy = core_items.artifact_energy_max(target)
        current = int(target.get("spirit_energy") or 0)
        missing = max_energy - current
        if missing <= 0:
            await interaction.response.send_message(
                f"Your artifact is already at full energy (**{max_energy}/{max_energy}**).",
                ephemeral=True,
            )
            return

        amount = min(missing, energy) if energy > 0 else missing
        cost = amount * core_items.ARTIFACT_RECHARGE_STONE_COST
        if int(me["spirit_stones"] or 0) < cost:
            await interaction.response.send_message(
                f"Recharging **{amount}** energy costs **{cost:,} 💎** — you only have "
                f"**{int(me['spirit_stones'] or 0):,}**.",
                ephemeral=True,
            )
            return

        now = datetime.now(timezone.utc)
        await self.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones-? WHERE id=?",
            (cost, me["id"]),
        )
        await self.bot.db.execute(
            "UPDATE items SET spirit_energy=?, spirit_energy_max=?, last_energy_at=?"
            " WHERE id=?",
            (current + amount, max_energy, now.isoformat(), target["id"]),
        )

        embed = discord.Embed(
            title=f"⚡ Artifact Recharged · 充能",
            description=(f"**{target['name']}**'s spirit energy surges: "
                         f"**{current} → {current + amount}** / {max_energy}."),
            color=ui.GOLD,
        )
        embed.add_field(name="Cost · 消耗", value=f"{cost:,} 💎", inline=True)
        await interaction.response.send_message(embed=embed)
