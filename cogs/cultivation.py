"""Core cultivation loop: register / cultivate / breakthrough / allocate / profile / leaderboard."""
from __future__ import annotations

import random
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from config import default as config
from core import affinities as aff
from core import dao_bonds, items as core_items, math as gm, sects
from db.queries import get_or_create_cultivator

_STAT_LABELS = {
    "physique": "体质 Physique",
    "spirit": "精神 Spirit",
    "luck": "气运 Luck",
    "comprehension": "悟性 Comprehension",
}


class CultivationCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ================================================================== /help
    @app_commands.command(
        name="help",
        description="Display command guide and descriptions for cultivators",
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="☯️ Core Cultivation", value="core"),
            app_commands.Choice(name="🌀 Spiritual Aptitudes", value="aptitudes"),
            app_commands.Choice(name="📦 Inventory & Items", value="items"),
            app_commands.Choice(name="🧪 Alchemy Crafting", value="alchemy"),
            app_commands.Choice(name="🌀 Reincarnation", value="reincarnation"),
            app_commands.Choice(name="🗡️ Secret Realms", value="realms"),
            app_commands.Choice(name="🌋 World Events", value="events"),
            app_commands.Choice(name="✨ Dao Laws", value="laws"),
            app_commands.Choice(name="🏪 Auction & Trade", value="market"),
            app_commands.Choice(name="🏯 Sects & Bonds", value="sects"),
        ]
    )
    async def help(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str] = None,
    ) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        cat_val = category.value if category else "overview"

        if cat_val == "overview":
            embed = discord.Embed(
                title=ui.format_title("🌌 Heavenly Dao Engine Command Manual · 指南", lang),
                description=(
                    "Welcome to the **Heavenly Dao Engine**! Select a category parameter in `/help category:<type>` to view detailed commands.\n\n"
                    "**Command Categories:**\n"
                    "• **`/help category:☯️ Core Cultivation`** — `/register`, `/cultivate`, `/daily`, `/breakthrough`, `/profile`, `/allocate`, `/leaderboard`\n"
                    "• **`/help category:🌀 Spiritual Aptitudes`** — `/aptitudes`\n"
                    "• **`/help category:📦 Inventory & Items`** — `/inventory`, `/equip`, `/use`, `/give`, `/item_info`\n"
                    "• **`/help category:🧪 Alchemy Crafting`** — `/recipes`, `/refine_pill`, `/alchemy_status`\n"
                    "• **`/help category:🌀 Reincarnation`** — `/reincarnate`, `/past_lives`, `/legacy`\n"
                    "• **`/help category:🗡️ Secret Realms`** — `/realms`, `/enter_realm`, `/explore`, `/retreat`\n"
                    "• **`/help category:🌋 World Events`** — `/events`, `/event_join`, `/event_attack`, `/event_status`, `/event_claim`\n"
                    "• **`/help category:✨ Dao Laws`** — `/laws`, `/comprehend`, `/law_status`\n"
                    "• **`/help category:🏪 Auction & Trade`** — `/market`, `/sell`, `/buy`, `/bid`, `/my_listings`, `/trade`\n"
                    "• **`/help category:🏯 Sects & Bonds`** — `/sect_create`, `/sect_join`, `/dao_bond`, `/dual_cultivate`"
                ),
                color=ui.GOLD,
            )
        elif cat_val == "aptitudes":
            embed = discord.Embed(
                title="🌀 Spiritual Aptitudes & Martial Intents",
                description=(
                    "• `/aptitudes` — Display your full Spiritual Root profile: Five Phases (五行), Martial Weapon Intents, Yin-Yang balance, dominant element, and dominant intent\n"
                    "• Aptitudes are revealed upon `/register` via a randomised awakening roll\n"
                    "• Grow your aptitudes through secret realms, alchemy elixirs, Dao Law comprehension, and World Boss victories\n"
                    "• High-tier scrolls and weapons require minimum aptitude values to equip"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "core":
            embed = discord.Embed(
                title=ui.format_title("☯️ Core Cultivation Commands", lang),
                description=(
                    "• `/register` — Awaken your cultivator persona, claim your starter kit, and enter the Heavenly Dao\n"
                    "• `/cultivate` — Absorb spiritual Qi into your dantian (cooldown shortens as you ascend)\n"
                    "• `/daily` — Claim a flat spirit-stone tribute every 20 hours (streak milestones)\n"
                    "• `/breakthrough` — Attempt to ascend to the next realm or layer\n"
                    "• `/transcend` — At the summit (Beyond Dao, 9th layer): shed your vessel for permanent gifts\n"
                    "• `/profile` — View your realm, Qi capacity, stats, titles, and physique\n"
                    "• `/allocate <stat> <points>` — Distribute stat points (physique, spirit, luck, comp)\n"
                    "• `/leaderboard` — View the server's top cultivators and realm rankings"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "items":
            embed = discord.Embed(
                title=ui.format_title("📦 Inventory & Items Commands", lang),
                description=(
                    "• `/inventory` — View your owned weapons, pills, scrolls, and materials\n"
                    "• `/equip <item_name>` — Equip weapons or technique scrolls\n"
                    "• `/use <item_name>` — Consume pills or talismans for temporary/permanent buffs\n"
                    "• `/give @user <item_name> [qty]` — Transfer items directly to another player\n"
                    "• `/item_info <item_name>` — Inspect item stats, grade, and effect data"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "alchemy":
            embed = discord.Embed(
                title=ui.format_title("🧪 Alchemy Crafting Commands", lang),
                description=(
                    "• `/recipes` — View available alchemy pill recipes and required ingredients\n"
                    "• `/refine_pill <recipe_name>` — Start 3-stage interactive pill crafting mini-game\n"
                    "• `/alchemy_status` — Check your alchemy mastery level, fame, and equipped cauldron"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "reincarnation":
            embed = discord.Embed(
                title=ui.format_title("🌀 Reincarnation Commands", lang),
                description=(
                    "• `/reincarnate` — Shed mortal vessel for legacy bonuses (Tier 5+)\n"
                    "• `/past_lives` — Inspect past reincarnation cycles, epitaphs, and memories\n"
                    "• `/legacy` — Preview retained stats, bonuses, and physique if reincarnating now"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "realms":
            embed = discord.Embed(
                title=ui.format_title("🗡️ Secret Realms Commands", lang),
                description=(
                    "• `/realms` — View available dungeon realms, entry costs, and potential drops\n"
                    "• `/enter_realm <realm_name>` — Open portal and enter a secret realm instance\n"
                    "• `/explore` — Explore next encounter node (Monster, Treasure, Trap, Herb Garden)\n"
                    "• `/retreat` — Safely retreat keeping all accumulated loot"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "events":
            embed = discord.Embed(
                title=ui.format_title("🌋 World Events Commands", lang),
                description=(
                    "• `/events` — List active and scheduled World Boss events\n"
                    "• `/event_join <event_id>` — Register participation in a World Event\n"
                    "• `/event_attack <event_id>` — Deal damage to the active World Boss\n"
                    "• `/event_status <event_id>` — Check boss HP bar, phase, and top damage leaderboard\n"
                    "• `/event_claim <event_id>` — Claim post-event loot rewards based on rank"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "laws":
            embed = discord.Embed(
                title=ui.format_title("✨ Dao Laws Commands", lang),
                description=(
                    "• `/laws` — Overview of fundamental laws, your mastery %, and active milestones\n"
                    "• `/comprehend <law_name>` — Meditate on a law to gain insight and mastery (Tier 5+)\n"
                    "• `/law_status <law_name>` — Inspect law lore, requirements, and milestone effects"
                ),
                color=ui.CYAN,
            )
        elif cat_val == "market":
            embed = discord.Embed(
                title=ui.format_title("🏪 Auction & Trade Commands", lang),
                description=(
                    "• `/market` — Browse active market listings in the Heavenly Auction House\n"
                    "• `/sell <item_name> <price>` — List item on market (5% listing fee)\n"
                    "• `/buy <listing_id>` — Instant buy item at buyout/listed price\n"
                    "• `/bid <listing_id> <amount>` — Place a bid on an active listing (+10% min increment)\n"
                    "• `/my_listings` — View your active market listings and top bids\n"
                    "• `/cancel_listing <listing_id>` — Cancel listing and retrieve item\n"
                    "• `/trade @user <item_name>` — Send direct P2P item trade offer\n"
                    "• `/trade_accept` / `/trade_decline` — Respond to pending trade proposals"
                ),
                color=ui.CYAN,
            )
        else:
            embed = discord.Embed(
                title=ui.format_title("🏯 Sects & Dao Bonds Commands", lang),
                description=(
                    "• `/sect_create <name>` — Form a new sect (500 spirit stones)\n"
                    "• `/sect_join <name>` / `/sect_leave` — Join or leave a sect\n"
                    "• `/sect_donate <amount>` / `/sect_upgrade` — Treasury donations & array upgrades\n"
                    "• `/dao_bond @user <type>` — Propose a companion/master-disciple bond\n"
                    "• `/dao_bonds` — View active bonds and affinity levels\n"
                    "• `/dual_cultivate @user` — Cultivate together with your bonded partner"
                ),
                color=ui.CYAN,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================== /register
    @app_commands.command(
        name="register",
        description="Awaken your cultivation and join the Heavenly Dao",
    )
    async def register(self, interaction: discord.Interaction) -> None:
        row, is_new = await get_or_create_cultivator(
            self.bot.db, interaction.user.id, interaction.user.display_name,
            interaction.guild_id,
        )
        # A chat message auto-creates the row before /register runs (passive Qi
        # listener). Those rows never rolled a Stored Qi pool — stored_qi_max is
        # 0 — so treat them as unawakened and run the full awakening here.
        if not is_new and (row.get("stored_qi_max") or 0) > 0:
            embed = discord.Embed(
                title="Already Awakened · 已觉醒",
                description=(
                    f"{interaction.user.mention}, your Dao heart already burns within the "
                    f"**{ui.realm_summary(row['realm_tier'], row['realm_sub_stage'])}**."
                ),
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # ── Roll Spiritual Aptitude Profile ───────────────────────────────
        profile = aff.generate_initial_aptitudes()
        db_fields = profile.to_db_dict()
        # Awakening also rolls the Stored Qi pool max (100-300, +50 Chaos Root)
        db_fields["stored_qi_max"] = gm.roll_stored_qi_max(profile)
        set_clause = ", ".join(f"{k}=?" for k in db_fields)
        await self.bot.db.execute(
            f"UPDATE cultivators SET {set_clause} WHERE id=?",
            (*db_fields.values(), row["id"]),
        )

        # ── Grant the free starting technique ─────────────────────────────
        import json as _json
        starter = await self.bot.db.fetchone(
            "SELECT * FROM techniques WHERE LOWER(name)=LOWER('Qi Burst')"
        )
        if starter:
            already = await self.bot.db.fetchone(
                "SELECT 1 FROM cultivator_techniques WHERE cultivator_id=? AND technique_id=?",
                (row["id"], starter["id"]),
            )
            if not already:
                from core import combat as core_cbt
                await self.bot.db.execute(
                    "INSERT INTO cultivator_techniques (cultivator_id, technique_id, entries)"
                    " VALUES (?,?,?)",
                    (row["id"], starter["id"], _json.dumps(core_cbt.roll_entries())),
                )

        # ── Starter kit: 100 💎 + a weapon + Qi pills (economy seed) ──────
        # STARTER_KIT carries full item specs, so no catalog lookup is needed.
        for name, item_type, grade, effect_data, qty in core_items.STARTER_KIT:
            await self.bot.db.execute(
                "INSERT INTO items (owner_id, name, item_type, grade, effect_data, quantity)"
                " VALUES (?,?,?,?,?,?)",
                (row["id"], name, item_type, grade, effect_data, qty),
            )
        await self.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?",
            (gm.STARTER_SPIRIT_STONES, row["id"]),
        )

        text = await self.bot.templates.get("register", name=interaction.user.display_name)
        embed = discord.Embed(title="☯ Dao Awakening · 觉醒", description=text, color=ui.GOLD)
        embed.add_field(
            name="Begin the Path",
            value=(
                "`/cultivate` to absorb 灵力 (spiritual qi) into your dantian.\n"
                "Chat in the server to gain passive Qi (capped at 25 messages/hour).\n"
                "When your 丹田 (dantian) is full, attempt `/breakthrough`.\n"
                "`/daily` every 20 hours for a spirit-stone tribute."
            ),
            inline=False,
        )
        embed.add_field(
            name="Starter Kit · 入门礼包",
            value=(
                f"**{gm.STARTER_SPIRIT_STONES} 💎 spirit stones** · Wooden Sword · "
                "3× Qi Gathering Pill"
            ),
            inline=False,
        )

        # ── Aptitude reveal ───────────────────────────────────────────────
        dom_el = profile.dominant_element()
        dom_in = profile.dominant_intent()
        el_meta = aff.ELEMENT_META[dom_el]
        in_meta = aff.INTENT_META[dom_in]
        apt_lines = []
        for key in aff.ELEMENT_KEYS:
            m = aff.ELEMENT_META[key]
            val = getattr(profile, key)
            apt_lines.append(f"{m['emoji']} **{m['name']}**: `{val}`")
        for key in aff.INTENT_KEYS:
            m = aff.INTENT_META[key]
            val = getattr(profile, key)
            apt_lines.append(f"{m['emoji']} **{m['name']}**: `{val}`")
        root_suffix = ""
        if profile.special_root == "chaos":
            root_suffix = "\n\n✨ **Chaos Five-Element Root (混沌五行根)** — You have awakened a legendary balanced root!"
        embed.add_field(
            name=f"Spiritual Root Revealed · 灵根觉醒",
            value="\n".join(apt_lines) + root_suffix,
            inline=False,
        )
        embed.add_field(
            name="Dominant Element",
            value=f"{el_meta['emoji']} {el_meta['name']} — {el_meta['effects']}",
            inline=True,
        )
        embed.add_field(
            name="Dominant Intent",
            value=f"{in_meta['emoji']} {in_meta['name']} — {in_meta['effects']}",
            inline=True,
        )
        embed.set_footer(text="Mortal Meridian · 凡人体质 | Realm 1/16 · 凡人一层")
        await interaction.response.send_message(embed=embed)

    # ============================================================= /cultivate
    @app_commands.command(
        name="cultivate",
        description="Meditate and absorb spiritual qi (30 min cooldown)",
    )
    async def cultivate(self, interaction: discord.Interaction) -> None:
        row, _ = await get_or_create_cultivator(
            self.bot.db, interaction.user.id, interaction.user.display_name,
            interaction.guild_id,
        )
        cooldown = gm.cultivate_cooldown_seconds(row["realm_tier"])
        if row["last_cultivate_at"]:
            last = ui.parse_db_time(row["last_cultivate_at"])
            if last:
                elapsed = (ui.now_utc() - last).total_seconds()
                if elapsed < cooldown:
                    remaining = cooldown - elapsed
                    embed = discord.Embed(
                        title="Meridians Aflame · 经脉灼热",
                        description=(
                            "Your meridians still thrum from the last cycle. Meditate again in "
                            f"**{ui.format_duration(remaining)}**."
                        ),
                        color=ui.CYAN,
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

        gain = gm.calculate_qi_gain(
            row["realm_tier"], row["comprehension"], source="cultivate",
            sect_array_level=await self.bot.sect_array_level(row["sect_id"]),
            has_sect=bool(row["sect_id"]),
            active_companions=await self.bot.active_companions(row["id"]),
            flat_bonus=row.get("transcendence_qi_gain_bonus", 0),
        )
        await self.bot.db.execute(
            "UPDATE cultivators SET qi_current = qi_current + ?, last_cultivate_at = ?"
            " WHERE id = ?",
            (gain, ui.now_str(), row["id"]),
        )

        text = await self.bot.templates.get(
            "cultivate", name=interaction.user.display_name,
            realm=ui.realm_summary(row["realm_tier"], row["realm_sub_stage"]),
        )
        new_qi = row["qi_current"] + gain
        embed = discord.Embed(title="🧘 Meditation · 修炼", description=text, color=ui.GOLD)
        embed.add_field(name="Qi Gained · 获得灵力", value=f"+{ui.format_qi(gain)}", inline=True)
        embed.add_field(
            name="Cooldown", value=ui.format_duration(cooldown),
            inline=True,
        )
        embed.add_field(
            name="Dantian · 丹田",
            value=(f"{ui.progress_bar(new_qi, row['qi_capacity'])} "
                   f"{ui.format_qi(new_qi)} / {ui.format_qi(row['qi_capacity'])}"),
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    # ================================================================= /daily
    @app_commands.command(
        name="daily",
        description="Claim your daily spirit-stone tribute (20h cooldown)",
    )
    async def daily(self, interaction: discord.Interaction) -> None:
        row, _ = await get_or_create_cultivator(
            self.bot.db, interaction.user.id, interaction.user.display_name,
            interaction.guild_id,
        )
        state = gm.daily_claim_state(
            row.get("last_daily_at"), row.get("daily_streak") or 0, ui.now_utc()
        )
        if not state["eligible"]:
            embed = discord.Embed(
                title="Tribute Not Yet Due · 供奉未至",
                description=(
                    "The mountain shrine is silent. The tribute renews in "
                    f"**{ui.format_duration(int(state['cooldown_left']))}**."
                ),
                color=ui.CYAN,
            )
            embed.add_field(
                name="Current Streak", value=f"{state['new_streak']} days", inline=True,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        stones = gm.daily_stones_for(row["realm_tier"])
        milestone_bonus = state["milestone_bonus"]
        total = stones + milestone_bonus
        # Atomic anti-race guard: the WHERE pins the value we just read, so a
        # near-simultaneous second claim (both fetched the same last_daily_at
        # before either UPDATE landed) matches 0 rows and never double-pays.
        prev = row.get("last_daily_at")
        cursor = await self.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones+?, last_daily_at=?,"
            " daily_streak=? WHERE id=? AND (last_daily_at IS ? OR last_daily_at = ?)",
            (total, ui.now_str(), state["new_streak"], row["id"], prev, prev),
        )
        if cursor.rowcount == 0:
            fresh = await self.bot.db.fetchone(
                "SELECT last_daily_at, daily_streak FROM cultivators WHERE id=?",
                (row["id"],),
            )
            fresh_state = gm.daily_claim_state(
                fresh["last_daily_at"] if fresh else None,
                fresh["daily_streak"] if fresh else 0,
                ui.now_utc(),
            )
            embed = discord.Embed(
                title="Tribute Not Yet Due · 供奉未至",
                description=(
                    "The mountain shrine is silent. The tribute renews in "
                    f"**{ui.format_duration(int(fresh_state['cooldown_left']))}**."
                ),
                color=ui.CYAN,
            )
            embed.add_field(
                name="Current Streak", value=f"{fresh_state['new_streak']} days", inline=True,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="⛰ Daily Tribute · 每日供奉",
            description=(
                f"The mountain shrine bestows its blessing upon you, "
                f"**{interaction.user.display_name}**."
            ),
            color=ui.GOLD,
        )
        embed.add_field(
            name="Spirit Stones · 灵石",
            value=f"+{total:,} 💎", inline=True,
        )
        embed.add_field(
            name="Streak · 连修", value=f"{state['new_streak']} days", inline=True,
        )
        if state["streak_broken"]:
            embed.add_field(
                name="Streak Reset · 道途中断",
                value="You missed over two days — the streak fell. Start anew.",
                inline=False,
            )
        elif milestone_bonus:
            embed.add_field(
                name="Milestone · 里程碑",
                value=f"🎉 **{state['new_streak']}-day streak bonus: +{milestone_bonus:,} 💎**",
                inline=False,
            )
        else:
            nxt = next(
                (m for m in sorted(gm.DAILY_STREAK_MILESTONES) if m > state["new_streak"]),
                None,
            )
            if nxt:
                embed.add_field(
                    name="Next Milestone",
                    value=f"{nxt}-day streak: +{gm.DAILY_STREAK_MILESTONES[nxt]:,} 💎",
                    inline=False,
                )
        embed.set_footer(
            text=f"Realm tribute: {gm.daily_stones_for(row['realm_tier']):,} 💎 · renews every 20 hours"
        )
        await interaction.response.send_message(embed=embed)

    # ========================================================== /breakthrough
    @app_commands.command(
        name="breakthrough",
        description="Attempt a breakthrough — the tribulation awaits",
    )
    async def breakthrough(self, interaction: discord.Interaction) -> None:
        row, _ = await get_or_create_cultivator(
            self.bot.db, interaction.user.id, interaction.user.display_name,
            interaction.guild_id,
        )
        if row["realm_tier"] >= gm.MAX_TIER and row["realm_sub_stage"] >= gm.MAX_LAYER:
            embed = discord.Embed(
                title="Summit Reached · 道之巅",
                description=(
                    f"{interaction.user.mention}, you stand at the **summit of cultivation** — "
                    "Beyond Dao 超脱 (9th Layer). The Dao has no further realms to offer... "
                    "but the **Heavens themselves** await. Use `/transcend` to shed this "
                    "vessel and begin a new cycle with permanent gifts."
                ),
                color=ui.GOLD,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if row["qi_current"] < row["qi_capacity"]:
            missing = row["qi_capacity"] - row["qi_current"]
            embed = discord.Embed(
                title="Dantian Unfull · 丹田未满",
                description=(
                    f"Your dantian holds {ui.format_qi(row['qi_current'])} of "
                    f"{ui.format_qi(row['qi_capacity'])}. Absorb **{ui.format_qi(missing)}**"
                    " more before daring the tribulation."
                ),
                color=ui.CRIMSON,
            )
            embed.add_field(
                name="Progress",
                value=f"{ui.progress_bar(row['qi_current'], row['qi_capacity'])}",
                inline=False,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Tier 8 -> Tier 9 Dao Fusion Gate check (Void Refinement inserted at 7)
        if row["realm_tier"] == 8 and row["realm_sub_stage"] == gm.MAX_LAYER:
            p_laws = await queries.cultivator_laws_all(self.bot.db, row["id"])
            from core import dao_laws as core_dl
            if not core_dl.has_dao_fusion_requirement(p_laws):
                embed = discord.Embed(
                    title="Dao Fusion Gate Sealed · 融合之门受阻",
                    description=(
                        "To achieve **Dao Fusion Ascension (Tier 8→9)**, you must reach **100% Complete Mastery** "
                        "in at least one Fundamental Dao Law! Use `/laws` and `/comprehend` to master a law."
                    ),
                    color=ui.CRIMSON,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        eq_rows = await self.bot.db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND is_equipped=1", (row["id"],)
        )
        eq_bonuses = core_items.calculate_equipped_bonuses([dict(r) for r in eq_rows])

        stats = {
            "physique": row["physique"] + eq_bonuses["stat_buffs"]["physique"],
            "spirit": row["spirit"] + eq_bonuses["stat_buffs"]["spirit"],
            "luck": row["luck"] + eq_bonuses["stat_buffs"]["luck"],
            "comprehension": row["comprehension"] + eq_bonuses["stat_buffs"]["comprehension"],
        }
        rage = (
            dao_bonds.RAGE_BREAKTHROUGH_BONUS
            if dao_bonds.is_raging(row["rage_breakthrough_bonus_until"])
            else 0.0
        )
        probability = gm.calculate_breakthrough_probability(
            stats, row["realm_tier"], row["realm_sub_stage"],
            heart_demon_ratio=row["heart_demon_ratio"],
            karma_points=row["karma_points"],
            has_sect=bool(row["sect_id"]),
            sect_array_level=await self.bot.sect_array_level(row["sect_id"]),
            failure_streak=row["failure_streak"],
            rage_bonus=rage + (eq_bonuses["breakthrough_aid"] / 100.0) + row.get("reincarnation_breakthrough_bonus", 0.0),
        )
        cfg = await self.bot._guild_config(interaction.guild_id)
        succeeded = random.random() < probability

        if succeeded:
            await self._on_success(interaction, row, probability, cfg)
        else:
            await self._on_failure(interaction, row, probability, cfg)

    async def _on_success(self, interaction, row, probability, cfg) -> None:
        new_tier, new_sub, tier_up = gm.next_realm_step(
            row["realm_tier"], row["realm_sub_stage"]
        )
        await self.bot.db.execute(
            "UPDATE cultivators SET realm_tier=?, realm_sub_stage=?, qi_current=0,"
            " qi_capacity=?, failure_streak=0, stat_points=?,"
            " spirit_stones=spirit_stones+? WHERE id=?",
            (new_tier, new_sub,
             gm.qi_capacity_for(new_tier) + row.get("transcendence_capacity_bonus", 0),
             row["stat_points"] + 2, sects.SPIRIT_STONES_PER_BREAKTHROUGH, row["id"]),
        )

        drops = core_items.roll_breakthrough_drops(row["realm_tier"])
        drop_names: list[str] = []
        for drop in drops:
            # Check existing unequipped stack
            existing = await self.bot.db.fetchone(
                "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) AND is_equipped=0",
                (row["id"], drop["name"].lower()),
            )
            if existing:
                await self.bot.db.execute("UPDATE items SET quantity=quantity+1 WHERE id=?", (existing["id"],))
            else:
                await self.bot.db.execute(
                    "INSERT INTO items (owner_id, name, item_type, grade, effect_data, quantity) VALUES (?,?,?,?,?,1)",
                    (row["id"], drop["name"], drop["item_type"], drop["grade"], drop["effect_data"]),
                )
            drop_names.append(f"{drop['name']} ({drop['grade']})")

        charm_dropped = None
        if random.random() < gm.CHARM_DROP_CHANCE:
            charm = random.choice(gm.CHARM_TYPES)
            await self.bot.db.execute(
                "INSERT INTO dao_protection_charms (owner_id, charm_type) VALUES (?,?)",
                (row["id"], charm),
            )
            charm_dropped = gm.CHARM_LABELS[charm]

        await self.bot.db.execute(
            "INSERT INTO breakthrough_log (cultivator_id, realm_tier, success,"
            " probability, heart_demon_ratio, was_erased) VALUES (?,?,1,?,?,0)",
            (row["id"], row["realm_tier"], probability, row["heart_demon_ratio"]),
        )

        text = await self.bot.templates.get(
            "breakthrough_success", name=interaction.user.display_name,
            realm=ui.realm_summary(new_tier, new_sub),
        )
        title = "⚡ Realm Ascension · 境界突破" if tier_up else "⛩ Breakthrough · 突破成功"
        embed = discord.Embed(title=title, description=text,
                              color=ui.PURPLE if tier_up else ui.GOLD)
        embed.add_field(name="New Realm", value=f"**{ui.realm_summary(new_tier, new_sub)}**", inline=True)
        embed.add_field(
            name="Reward",
            value=f"+2 stat points · {sects.SPIRIT_STONES_PER_BREAKTHROUGH} 💎 spirit stones",
            inline=True,
        )
        if charm_dropped:
            embed.add_field(name="Fortune · 机缘", value=f"Found **{charm_dropped}**", inline=False)
        if drop_names:
            embed.add_field(name="Loot · 宝物", value=", ".join(drop_names), inline=False)
        embed.set_footer(text=f"Success chance was {probability:.0%}")
        await interaction.response.send_message(embed=embed)

    async def _on_failure(self, interaction, row, probability, cfg) -> None:
        halved_qi = row["qi_current"] // 2  # invariant 50% failure penalty
        updates: dict[str, object] = {
            "qi_current": halved_qi,
            "failure_streak": row["failure_streak"] + 1,
        }
        text_cat = "breakthrough_fail"
        title = "🌑 Breakthrough Failed · 突破失败"
        color = ui.CRIMSON
        backlash = row["heart_demon_ratio"] > 0.35 and random.random() < row["heart_demon_ratio"]

        if backlash:
            new_tier, new_sub = row["realm_tier"], row["realm_sub_stage"]
            if new_sub > 1:
                new_sub -= 1
            elif new_tier > 1:
                new_tier -= 1
                new_sub = gm.MAX_LAYER
            updates.update({
                "realm_tier": new_tier, "realm_sub_stage": new_sub,
                "karma_points": row["karma_points"] - 50,
                "heart_demon_ratio": min(1.0, row["heart_demon_ratio"] + 0.08),
            })
            text_cat = "heart_demon_backlash"
            title = "😈 Heart Demon Backlash · 心魔反噬"
            color = ui.OBSIDIAN

        was_erased = 0
        if gm.erasure_should_roll(row["realm_tier"], bool(cfg["erasure_enabled"])) and gm.roll_erasure():
            charm = await self.bot.db.fetchone(
                "SELECT * FROM dao_protection_charms WHERE owner_id=? AND consumed_at IS NULL"
                " ORDER BY id LIMIT 1",
                (row["id"],),
            )
            result = gm.resolve_erasure(charm["charm_type"] if charm else None)
            if result["charm_consumed"] and charm:
                await self.bot.db.execute(
                    "UPDATE dao_protection_charms SET consumed_at=? WHERE id=?",
                    (ui.now_str(), charm["id"]),
                )
            new_stats = gm.apply_erasure_to_stats(
                {"physique": row["physique"], "spirit": row["spirit"],
                 "luck": row["luck"], "comprehension": row["comprehension"]},
                result["keep_stats"],
            )
            updates.update({
                "realm_tier": 1 if result["erased"] else row["realm_tier"],
                "realm_sub_stage": 1 if result["erased"] else row["realm_sub_stage"],
                "qi_current": int(halved_qi * result["qi_refund"]),
                "qi_capacity": (
                    gm.qi_capacity_for(1) + row.get("transcendence_capacity_bonus", 0)
                    if result["erased"] else row["qi_capacity"]
                ),
                "comprehension": new_stats["comprehension"],
                "luck": new_stats["luck"],
                "heart_demon_ratio": max(
                    0.0, min(1.0, row["heart_demon_ratio"] + result["heart_demon_delta"])
                ),
                "reincarnation_cycle": row["reincarnation_cycle"] + (1 if result["erased"] else 0),
            })
            if result["erased"]:
                # Fallen to Mortal: fresh start — no mercy carryover, no unspent pool
                updates["failure_streak"] = 0
                updates["stat_points"] = 0
                # Log to reincarnation_log
                from core import reincarnation as core_reinc
                epitaph = core_reinc.generate_epitaph(row)
                await self.bot.db.execute(
                    "INSERT INTO reincarnation_log (cultivator_id, cycle_from, cycle_to, reason, realm_tier_at_death, realm_sub_stage_at_death, comprehension_retained, luck_retained, technique_retained, epitaph)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (row["id"], row["reincarnation_cycle"], row["reincarnation_cycle"] + 1, "erasure", row["realm_tier"], row["realm_sub_stage"], new_stats["comprehension"] - 10, new_stats["luck"] - 5, None, epitaph),
                )
            if result["title"]:
                updates["titles"] = ui.add_json_title(row["titles"], result["title"])
            was_erased = 1
            text_cat = "erasure"
            title = "☠ Heavenly Dao Erasure · 天道抹除"
            color = ui.OBSIDIAN

        set_clause = ", ".join(f"{key}=?" for key in updates)
        await self.bot.db.execute(
            f"UPDATE cultivators SET {set_clause} WHERE id=?",
            tuple(list(updates.values()) + [row["id"]]),
        )
        await self.bot.db.execute(
            "INSERT INTO breakthrough_log (cultivator_id, realm_tier, success,"
            " probability, heart_demon_ratio, was_erased) VALUES (?,?,0,?,?,?)",
            (row["id"], row["realm_tier"], probability, row["heart_demon_ratio"], was_erased),
        )

        final_tier = int(updates.get("realm_tier", row["realm_tier"]))
        final_sub = int(updates.get("realm_sub_stage", row["realm_sub_stage"]))
        text = await self.bot.templates.get(
            text_cat, name=interaction.user.display_name,
            realm=ui.realm_summary(final_tier, final_sub),
        )
        embed = discord.Embed(title=title, description=text, color=color)
        embed.add_field(name="Qi Remaining · 余下灵力", value=ui.format_qi(updates["qi_current"]), inline=True)
        embed.add_field(name="Dao Mercy · 天道怜悯", value=f"+5% next attempt (max +25%)", inline=True)
        if was_erased:
            embed.add_field(
                name="Legacy · 遗蜕",
                value="You keep 25% 悟性 (comprehension) and 10% 气运 (luck) as past-life wisdom.",
                inline=False,
            )
        embed.set_footer(text=f"Success chance was {probability:.0%}")
        await interaction.response.send_message(embed=embed)

    # ============================================================== /allocate
    @app_commands.command(
        name="allocate",
        description="Distribute stat points earned from breakthroughs",
    )
    async def allocate(
        self,
        interaction: discord.Interaction,
        stat: Literal["physique", "spirit", "luck", "comprehension"],
        amount: int = 1,
    ) -> None:
        row, _ = await get_or_create_cultivator(
            self.bot.db, interaction.user.id, interaction.user.display_name,
            interaction.guild_id,
        )
        if amount < 1:
            await interaction.response.send_message("Amount must be at least 1.", ephemeral=True)
            return
        if row["stat_points"] < amount:
            embed = discord.Embed(
                title="Insufficient Points · 悟道点不足",
                description=f"You have {row['stat_points']} stat points available.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        new_value = row[stat] + amount
        await self.bot.db.execute(
            f"UPDATE cultivators SET {stat}=?, stat_points=stat_points-? WHERE id=?",
            (new_value, amount, row["id"]),
        )
        embed = discord.Embed(
            title="Stat Forged · 加点完成",
            description=f"**{_STAT_LABELS[stat]}** raised to **{new_value}**.",
            color=ui.GOLD,
        )
        embed.add_field(
            name="Remaining Points",
            value=str(row["stat_points"] - amount),
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    # =============================================================== /profile
    @app_commands.command(name="profile", description="View your cultivation profile")
    async def profile(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        target = member or interaction.user
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE user_id=?", (target.id,)
        )
        if not row:
            embed = discord.Embed(
                title="Unawakened · 未觉醒",
                description=f"{target.mention} has not yet `/register`ed.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        bonds = await self.bot.db.fetchone(
            "SELECT COUNT(*) AS c FROM dao_bonds"
            " WHERE status IN ('forming','active')"
            " AND (cultivator_a_id=? OR cultivator_b_id=?)",
            (row["id"], row["id"]),
        )
        charms = await self.bot.db.fetchone(
            "SELECT COUNT(*) AS c FROM dao_protection_charms WHERE owner_id=? AND consumed_at IS NULL",
            (row["id"],),
        )
        sect_name = None
        if row["sect_id"]:
            sect = await self.bot.db.fetchone("SELECT name FROM sects WHERE id=?", (row["sect_id"],))
            sect_name = sect["name"] if sect else None
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        stats_str = (
            f"Physique {row['physique']} | Spirit {row['spirit']} | Luck {row['luck']} | Comprehension {row['comprehension']}"
            if lang == "english"
            else f"体质 {row['physique']} | 精神 {row['spirit']} | 气运 {row['luck']} | 悟性 {row['comprehension']}"
        )

        title_suffix = row['title'] or ('Nameless Wanderer' if lang == 'english' else '无名散修 Nameless Wanderer')

        embed = discord.Embed(
            title=ui.format_title(f"{row['username']} · {title_suffix}", lang),
            description=ui.realm_summary(row["realm_tier"], row["realm_sub_stage"], lang),
            color=ui.CYAN,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name=ui.format_title("Dantian · 丹田", lang),
            value=(f"{ui.progress_bar(row['qi_current'], row['qi_capacity'])}\n"
                   f"{ui.format_qi(row['qi_current'], lang)} / {ui.format_qi(row['qi_capacity'], lang)}"),
            inline=False,
        )
        sq_max = gm.stored_qi_effective_max(row["stored_qi_max"], row["stored_qi_max_bonus"])
        embed.add_field(
            name=ui.format_title("Stored Qi · 存灵气", lang),
            value=(f"{ui.progress_bar(row['stored_qi_current'], sq_max)}\n"
                   f"{row['stored_qi_current']} / {sq_max}"
                   f" · regen {gm.stored_qi_regen_per_hour(row['stored_qi_regen_bonus'])}/h"),
            inline=False,
        )
        embed.add_field(
            name=ui.format_title("Stats · 属性", lang),
            value=f"{stats_str}\n`{row['stat_points']}` unspent points",
            inline=False,
        )
        embed.add_field(name=ui.format_title("Karma · 业力", lang), value=str(row["karma_points"]), inline=True)
        embed.add_field(
            name=ui.format_title("Heart Demon · 心魔", lang),
            value=f"{gm.heart_demon_points(row['heart_demon_ratio'])}/{gm.HD_POINTS_MAX}",
            inline=True,
        )
        embed.add_field(
            name=ui.format_title("Sect · 宗门", lang),
            value=sect_name or ("None" if lang == "english" else "None · 无"),
            inline=True,
        )
        embed.add_field(name=ui.format_title("Dao Bonds · 道契", lang), value=str(bonds["c"] if bonds else 0), inline=True)
        embed.add_field(name=ui.format_title("Charms · 护符", lang), value=str(charms["c"] if charms else 0), inline=True)
        embed.add_field(name=ui.format_title("Reincarnations · 轮回", lang), value=str(row["reincarnation_cycle"]), inline=True)
        embed.add_field(name=ui.format_title("Spirit Stones · 灵石", lang), value=f"{row['spirit_stones']:,} 💎", inline=True)
        embed.add_field(name=ui.format_title("Alchemy Mastery · 丹道造诣", lang), value=f"Lvl {dict(row).get('alchemy_mastery', 0)}", inline=True)
        titles = ui.parse_json_list(row["titles"])
        embed.add_field(
            name=ui.format_title("Titles · 称号", lang),
            value=", ".join(titles) if titles else "None",
            inline=False,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # =========================================================== /leaderboard
    @app_commands.command(
        name="leaderboard",
        description="The mightiest cultivators of this realm",
    )
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.fetchall(
            "SELECT username, realm_tier, realm_sub_stage, qi_current, karma_points"
            " FROM cultivators WHERE last_active_guild_id=?"
            " ORDER BY realm_tier DESC, realm_sub_stage DESC, qi_current DESC, karma_points DESC"
            " LIMIT 10",
            (interaction.guild_id,),
        )
        if not rows:
            embed = discord.Embed(
                title="Leaderboard · 榜单",
                description="The world is silent. No cultivators have awakened yet.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed)
            return
        embed = discord.Embed(
            title="🏆 Heavenly Leaderboard · 强者榜",
            description="The mightiest cultivators of this realm",
            color=ui.GOLD,
        )
        lines = []
        for idx, row in enumerate(rows, start=1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"`{idx}.`")
            lines.append(
                f"{medal} **{row['username']}** — {ui.realm_summary(row['realm_tier'], row['realm_sub_stage'])}"
                f" · {ui.format_qi(row['qi_current'])}"
            )
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)
