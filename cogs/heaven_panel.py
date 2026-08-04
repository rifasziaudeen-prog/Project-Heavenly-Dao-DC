"""Heaven Panel — the admin arbiter's command center.

`/heaven_panel` shows server-wide stats and one-click divine actions:
  * Dao Punish   — strip Qi / reset Qi / demote realm / raise Heart Demon / Karma strike
  * Dao Bless    — grant Qi / grant a charm / Karma grace / clear Heart Demon / stat points
  * Spawn Event  — schedule a Heavenly Calamity (scheduler activates it later)
  * Broadcast    — announce a decree from the Heaven
"""
from __future__ import annotations

import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import anti_cheat, math as gm
from db.queries import get_or_create_cultivator

EVENT_TYPES = {
    "demon_beast_siege": "妖兽围城 · Demon Beast Siege",
    "heavenly_tribulation_rain": "天劫之雨 · Tribulation Rain",
    "ancient_ruin_awakening": "上古遗迹 · Ancient Ruin Awakening",
    "sect_war": "宗门大战 · Sect War",
}
DELAYS = {"1h": 1, "4h": 4, "12h": 12, "24h": 24}


def _cultivator_options(rows: list, placeholder: str, on_pick):
    options = [
        discord.SelectOption(
            label=f"{r['username'][:24]} · {gm.realm_name(r['realm_tier'])}",
            value=str(r["id"]),
        )
        for r in rows
    ]
    return _CultivatorSelect(options, placeholder, on_pick)


class _CultivatorSelect(discord.ui.Select):
    def __init__(self, options, placeholder, on_pick) -> None:
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self._on_pick = on_pick

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_pick(interaction, int(self.values[0]))


class _SimpleSelect(discord.ui.Select):
    def __init__(self, options, placeholder, on_pick) -> None:
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self._on_pick = on_pick

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_pick(interaction, self.values[0])


class HeavenPanelCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------- helpers
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

    async def _deny(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="⛔ Mortal Presumption · 凡人之妄",
            description="Only the Heaven may command. This power is barred to you.",
            color=ui.CRIMSON,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _top_cultivators(self, guild_id: int, limit: int = 25) -> list:
        return await self.bot.db.fetchall(
            "SELECT id, username, realm_tier, realm_sub_stage, qi_current,"
            " stat_points, karma_points, heart_demon_ratio"
            " FROM cultivators WHERE guild_id=?"
            " ORDER BY realm_tier DESC, realm_sub_stage DESC, qi_current DESC LIMIT ?",
            (guild_id, limit),
        )

    # ------------------------------------------------------------ the panel
    @app_commands.command(
        name="heaven_panel",
        description="Open the Heavenly Dao administrative panel (admin only)",
    )
    async def heaven_panel(self, interaction: discord.Interaction) -> None:
        if not await self._is_admin(interaction):
            await self._deny(interaction)
            return
        embed = await self._stats_embed(interaction.guild_id)
        view = PanelView(self)
        # Ephemeral: the embed shows flagged users and server stats — only the
        # Heaven (admin) should ever see them.
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _stats_embed(self, guild_id: int) -> discord.Embed:
        db = self.bot.db
        cult = await db.fetchone(
            "SELECT COUNT(*) AS c, AVG(realm_tier) AS avg_tier,"
            " SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS today"
            " FROM cultivators WHERE guild_id=?",
            (ui.now_utc().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), guild_id),
        )
        hour_bucket = ui.now_utc().strftime("%Y-%m-%d %H:00:00")
        last_hour = await db.fetchone(
            "SELECT COALESCE(SUM(message_count),0) AS mc, COALESCE(SUM(qi_total),0) AS qt"
            " FROM qi_hourly_stats WHERE guild_id=? AND hour_bucket >= ?",
            (guild_id, hour_bucket),
        )
        day_start = (ui.now_utc() - timedelta(hours=24)).strftime("%Y-%m-%d %H:00:00")
        last_day = await db.fetchone(
            "SELECT COALESCE(SUM(message_count),0) AS mc, COALESCE(SUM(qi_total),0) AS qt"
            " FROM qi_hourly_stats WHERE guild_id=? AND hour_bucket >= ?",
            (guild_id, day_start),
        )
        flags = await anti_cheat.unresolved_count(db, guild_id)
        events = await db.fetchone(
            "SELECT COUNT(*) AS c FROM world_events WHERE guild_id=?"
            " AND status IN ('pending','active')",
            (guild_id,),
        )
        cfg = await self.bot._guild_config(guild_id)

        embed = discord.Embed(
            title="⛰ Heavenly Dao Panel · 天道面板",
            description="You are the Heaven that makes the Earth. Wield the Dao wisely.",
            color=ui.GOLD,
        )
        embed.add_field(
            name="Cultivators · 修士",
            value=(f"**{cult['c']}** total (avg realm {float(cult['avg_tier'] or 1):.1f})"
                   f"\n{int(cult['today'] or 0)} awakened today"),
            inline=True,
        )
        embed.add_field(
            name="Qi Throughput · 灵力吞吐",
            value=(f"last hour: {last_hour['mc']} msgs / {ui.format_qi(last_hour['qt'])}"
                   f"\n24h: {last_day['mc']} msgs / {ui.format_qi(last_day['qt'])}"),
            inline=True,
        )
        embed.add_field(
            name="Calamities · 天劫",
            value=f"{int(events['c'] or 0)} scheduled/active",
            inline=True,
        )
        embed.add_field(
            name="Anti-Cheat · 天眼",
            value=f"**{flags}** unresolved flag(s)" if flags else "No flags · 清平世界",
            inline=True,
        )
        embed.add_field(
            name="Doctrine · 天道律法",
            value=f"Erasure: {'on · 开' if cfg['erasure_enabled'] else 'off · 关'}"
                  f" | Groq: {'on' if cfg['groq_enabled'] else 'off'}",
            inline=True,
        )
        recent = await anti_cheat.recent_flags(db, guild_id, limit=5)
        if recent:
            lines = [
                f"• <@{f['user_id']}> — {f['flag_type']} ({'minor' if f['severity'] == 1 else 'major'})"
                for f in recent
            ]
            embed.add_field(name="Recent Flags · 最近疑点", value="\n".join(lines), inline=False)
        embed.set_footer(text="Buttons below grant you the power of the Heaven")
        return embed

    # ----------------------------------------------------------- Dao Punish
    async def punish_flow(self, interaction: discord.Interaction) -> None:
        rows = await self._top_cultivators(interaction.guild_id)
        if not rows:
            await interaction.response.send_message(
                "No cultivators have awakened yet.", ephemeral=True
            )
            return
        view = discord.ui.View(timeout=180)
        view.add_item(_cultivator_options(
            rows, "Whom shall the Heaven punish?", self._punish_pick
        ))
        await interaction.response.send_message(
            "**⛰ Dao Punish · 天道惩处** — who has offended the Heaven?",
            view=view, ephemeral=True,
        )

    async def _punish_pick(self, interaction: discord.Interaction, cultivator_id: int) -> None:
        punishments = {
            "strip_50": "Strip 50% Qi · 削去半数灵力",
            "reset_qi": "Reset Qi to zero · 灵力归零",
            "demote": "Demote one sub-stage · 境界跌落",
            "heart_demon": "Raise Heart Demon +0.2 · 心魔滋生",
            "karma_strike": "Karma strike −200 · 业力打击",
        }
        view = discord.ui.View(timeout=180)
        view.add_item(_SimpleSelect(
            [discord.SelectOption(label=v, value=k) for k, v in punishments.items()],
            "Choose the punishment", lambda i, v: self._punish_apply(i, cultivator_id, v),
        ))
        await interaction.response.edit_message(content="**⛰ Dao Punish** — choose the sentence:", view=view)

    async def _punish_apply(self, interaction: discord.Interaction, cultivator_id: int, punishment: str) -> None:
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE id=?", (cultivator_id,)
        )
        if not row:
            await interaction.response.edit_message(content="Cultivator no longer exists.", view=None)
            return
        updates: dict[str, object] = {}
        notes = {
            "strip_50": "50% of Qi stripped",
            "reset_qi": "Qi reduced to zero",
            "demote": "Realm demoted one sub-stage",
            "heart_demon": "Heart Demon raised to "
                           f"{min(1.0, row['heart_demon_ratio'] + 0.2):.0%}",
            "karma_strike": "Karma reduced by 200",
        }
        if punishment == "strip_50":
            updates["qi_current"] = row["qi_current"] // 2
        elif punishment == "reset_qi":
            updates["qi_current"] = 0
        elif punishment == "demote":
            new_tier, new_sub = row["realm_tier"], row["realm_sub_stage"]
            if new_sub > 1:
                new_sub -= 1
            elif new_tier > 1:
                new_tier -= 1
                new_sub = 4
            updates.update({"realm_tier": new_tier, "realm_sub_stage": new_sub})
        elif punishment == "heart_demon":
            updates["heart_demon_ratio"] = min(1.0, row["heart_demon_ratio"] + 0.2)
        elif punishment == "karma_strike":
            updates["karma_points"] = row["karma_points"] - 200

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            await self.bot.db.execute(
                f"UPDATE cultivators SET {set_clause} WHERE id=?",
                tuple(list(updates.values()) + [row["id"]]),
            )
        await self.bot.add_flag(
            interaction.guild_id, row["user_id"], "dao_punished",
            f"Heaven punished {row['username']} ({punishment})",
        )
        text = await self.bot.templates.get("dao_punish", name=row["username"])
        embed = discord.Embed(title="⚡ Dao Punishment Executed · 天道已惩", description=text, color=ui.CRIMSON)
        embed.add_field(name="Target · 受刑者", value=f"<@{row['user_id']}>", inline=True)
        embed.add_field(name="Sentence · 刑罚", value=notes.get(punishment, punishment), inline=True)
        embed.add_field(name="Heaven · 天道", value=f"<@{interaction.user.id}>", inline=True)
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    # ------------------------------------------------------------ Dao Bless
    async def bless_flow(self, interaction: discord.Interaction) -> None:
        rows = await self._top_cultivators(interaction.guild_id)
        if not rows:
            await interaction.response.send_message(
                "No cultivators have awakened yet.", ephemeral=True
            )
            return
        view = discord.ui.View(timeout=180)
        view.add_item(_cultivator_options(rows, "Who shall receive Heaven's grace?", self._bless_pick))
        await interaction.response.send_message(
            "**✨ Dao Bless · 天道赐福** — who shall receive Heaven's grace?",
            view=view, ephemeral=True,
        )

    async def _bless_pick(self, interaction: discord.Interaction, cultivator_id: int) -> None:
        blessings = {
            "qi_1000": "Grant 1,000 Qi · 赐予灵力",
            "charm": "Grant a protection charm · 赐予护符",
            "karma": "Karma grace +100 · 业力宽恕",
            "clear_hd": "Clear Heart Demon · 心魔驱散",
            "stat_5": "Grant 5 stat points · 赐予悟道点",
        }
        view = discord.ui.View(timeout=180)
        view.add_item(_SimpleSelect(
            [discord.SelectOption(label=v, value=k) for k, v in blessings.items()],
            "Choose the blessing", lambda i, v: self._bless_apply(i, cultivator_id, v),
        ))
        await interaction.response.edit_message(content="**✨ Dao Bless** — choose the grace:", view=view)

    async def _bless_apply(self, interaction: discord.Interaction, cultivator_id: int, blessing: str) -> None:
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE id=?", (cultivator_id,)
        )
        if not row:
            await interaction.response.edit_message(content="Cultivator no longer exists.", view=None)
            return
        notes = {
            "qi_1000": "+1,000 Qi granted",
            "charm": "A dao protection charm bestowed",
            "karma": "Karma increased by 100",
            "clear_hd": "Heart Demon cleared to zero",
            "stat_5": "5 stat points granted",
        }
        if blessing == "qi_1000":
            await self.bot.db.execute(
                "UPDATE cultivators SET qi_current = qi_current + 1000 WHERE id=?", (row["id"],)
            )
        elif blessing == "charm":
            charm = random.choice(gm.CHARM_TYPES)
            await self.bot.db.execute(
                "INSERT INTO dao_protection_charms (owner_id, charm_type) VALUES (?,?)",
                (row["id"], charm),
            )
        elif blessing == "karma":
            await self.bot.db.execute(
                "UPDATE cultivators SET karma_points = karma_points + 100 WHERE id=?", (row["id"],)
            )
        elif blessing == "clear_hd":
            await self.bot.db.execute(
                "UPDATE cultivators SET heart_demon_ratio = 0 WHERE id=?", (row["id"],)
            )
        elif blessing == "stat_5":
            await self.bot.db.execute(
                "UPDATE cultivators SET stat_points = stat_points + 5 WHERE id=?", (row["id"],)
            )
        text = await self.bot.templates.get("dao_bless", name=row["username"])
        embed = discord.Embed(title="✨ Dao Blessing Bestowed · 天道赐福", description=text, color=ui.GOLD)
        embed.add_field(name="Target · 受恩者", value=f"<@{row['user_id']}>", inline=True)
        embed.add_field(name="Grace · 恩赐", value=notes.get(blessing, blessing), inline=True)
        embed.add_field(name="Heaven · 天道", value=f"<@{interaction.user.id}>", inline=True)
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    # ---------------------------------------------------------- Spawn Event
    async def event_flow(self, interaction: discord.Interaction) -> None:
        view = discord.ui.View(timeout=180)
        view.add_item(_SimpleSelect(
            [discord.SelectOption(label=v, value=k) for k, v in EVENT_TYPES.items()],
            "Choose the calamity", lambda i, v: self._event_pick(i, v),
        ))
        await interaction.response.send_message(
            "**⚡ Spawn Event · 天降大劫** — which calamity shall shake this realm?",
            view=view, ephemeral=True,
        )

    async def _event_pick(self, interaction: discord.Interaction, event_type: str) -> None:
        view = discord.ui.View(timeout=180)
        view.add_item(_SimpleSelect(
            [discord.SelectOption(label=f"In {hours}h · {hours}小时后", value=str(hours))
             for hours in DELAYS.values()],
            "When shall it strike?", lambda i, v: self._event_schedule(interaction, event_type, int(v)),
        ))
        await interaction.response.edit_message(content="**⚡ Spawn Event** — when shall it strike?", view=view)

    async def _event_schedule(self, interaction: discord.Interaction, event_type: str, hours: int) -> None:
        from datetime import datetime, timezone

        scheduled = datetime.now(timezone.utc) + timedelta(hours=hours)
        await self.bot.db.execute(
            "INSERT INTO world_events (guild_id, event_type, scheduled_at, difficulty_rating)"
            " VALUES (?,?,?,1)",
            (interaction.guild_id, event_type, scheduled.strftime("%Y-%m-%d %H:%M:%S")),
        )
        text = await self.bot.templates.get("world_event", name=EVENT_TYPES[event_type])
        embed = discord.Embed(
            title=f"⚡ Heavenly Calamity Scheduled · 天劫已定",
            description=text, color=ui.CRIMSON,
        )
        embed.add_field(name="Calamity · 劫难", value=EVENT_TYPES[event_type], inline=True)
        embed.add_field(name="Strikes in", value=f"{hours}h · {hours}小时后", inline=True)
        embed.add_field(name="Status", value="Pending · 待降", inline=True)
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    # ------------------------------------------------------------ Broadcast
    async def broadcast_flow(self, interaction: discord.Interaction) -> None:
        modal = _BroadcastModal(self)
        await interaction.response.send_modal(modal)

    async def _broadcast_send(self, interaction: discord.Interaction, text: str) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        channel = None
        if cfg["broadcast_channel_id"] and interaction.guild:
            channel = interaction.guild.get_channel(cfg["broadcast_channel_id"])
        channel = channel or interaction.channel
        embed = discord.Embed(
            title="☯ Decree of the Heaven · 天道法旨",
            description=text, color=ui.GOLD,
        )
        embed.set_footer(text=f"Decreed by {interaction.user.display_name}")
        await channel.send(embed=embed)
        embed2 = discord.Embed(
            title="📣 Decree Broadcast · 法旨已宣",
            description=f"Delivered to {channel.mention}.",
            color=ui.GOLD,
        )
        await interaction.response.send_message(embed=embed2, ephemeral=True)


class _BroadcastModal(discord.ui.Modal):
    def __init__(self, cog) -> None:
        super().__init__(title="Heavenly Decree · 天道法旨")
        self.cog = cog
        self.add_item(discord.ui.TextInput(
            label="Decree message",
            style=discord.TextStyle.paragraph,
            placeholder="The Heaven proclaims...",
            max_length=2000,
        ))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog._broadcast_send(interaction, self.children[0].value or "")


class PanelView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.add_item(_RefreshButton(cog))
        self.add_item(_PunishButton(cog))
        self.add_item(_BlessButton(cog))
        self.add_item(_EventButton(cog))
        self.add_item(_BroadcastButton(cog))


class _RefreshButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.cog._is_admin(interaction):
            await self.cog._deny(interaction)
            return
        embed = await self.cog._stats_embed(interaction.guild_id)
        await interaction.response.defer()
        await interaction.edit_original_response(embed=embed)


class _PunishButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Dao Punish", style=discord.ButtonStyle.danger, emoji="⛰")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.cog._is_admin(interaction):
            await self.cog._deny(interaction)
            return
        await self.cog.punish_flow(interaction)


class _BlessButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Dao Bless", style=discord.ButtonStyle.success, emoji="✨")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.cog._is_admin(interaction):
            await self.cog._deny(interaction)
            return
        await self.cog.bless_flow(interaction)


class _EventButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Spawn Event", style=discord.ButtonStyle.primary, emoji="⚡")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.cog._is_admin(interaction):
            await self.cog._deny(interaction)
            return
        await self.cog.event_flow(interaction)


class _BroadcastButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Broadcast", style=discord.ButtonStyle.primary, emoji="📣")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.cog._is_admin(interaction):
            await self.cog._deny(interaction)
            return
        await self.cog.broadcast_flow(interaction)
