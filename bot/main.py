"""Heavenly Dao Engine — Discord bot assembly and background tasks.

Background tasks (all start on ready):
  * qi flush       — memory-buffered message Qi -> qi_buffer + cultivators (60s)
  * presence       — "Watching over N realms | M cultivators" (5 min)
  * backup         — daily SQLite snapshot to backups/
  * world events   — activates due scheduled events (30s poll)
  * market expiry  — expires due auction listings: refunds escrow, returns items (60s)
"""
from __future__ import annotations

import logging
from collections import defaultdict

import discord
from discord.ext import commands, tasks

from bot import utils as ui
from config import default as config
from core import anti_cheat, math as gm
from core.groq_client import GroqClient
from core.template_engine import TemplateEngine
from db.database import Database, backup_database, run_migrations
from db.seeds import seed_templates_if_empty

log = logging.getLogger("heavenly_dao")


class HeavenlyDaoBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # required for passive Qi
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the mortal world stir",
            ),
        )
        self.db = Database(config.DATABASE_PATH)
        self.templates = TemplateEngine(self.db)
        self.groq = GroqClient(
            api_key=config.GROQ_API_KEY, db=self.db, enabled=config.ENABLE_GROQ
        )
        # In-memory message Qi buffer (pillar 1: zero-latency async core).
        # Lost on crash — acceptable for v1 (documented in MIGRATION.md).
        self.qi_buffer: list[dict] = []
        self._last_msg: dict[tuple[int, int], tuple[str, float]] = {}
        self._deny_counts: dict[tuple[int, int], tuple[int, str]] = {}
        self._started = False

    # ------------------------------------------------------------------ setup
    async def setup_hook(self) -> None:
        await self.db.connect()
        applied = await run_migrations(self.db)
        if applied:
            log.info("Applied migrations: %s", applied)
        seeded = await seed_templates_if_empty(self.db)
        if seeded:
            log.info("Seeded %d narrative templates", seeded)
        await self.templates.load()

        from cogs.affinities import AffinitiesCog
        from cogs.alchemy import AlchemyCog
        from cogs.auction import AuctionCog
        from cogs.cultivation import CultivationCog
        from cogs.dao_bonds import DaoBondsCog
        from cogs.dao_config import DaoConfigCog
        from cogs.dao_laws import DaoLawsCog
        from cogs.heaven_panel import HeavenPanelCog
        from cogs.items import ItemsCog
        from cogs.passive_qi import PassiveQiCog
        from cogs.reaction_roles import ReactionRolesCog
        from cogs.reincarnation import ReincarnationCog
        from cogs.secret_realms import SecretRealmsCog
        from cogs.sects import SectsCog
        from cogs.transcendence import TranscendenceCog
        from cogs.world_events import WorldEventsCog

        await self.add_cog(CultivationCog(self))
        await self.add_cog(AffinitiesCog(self))
        await self.add_cog(PassiveQiCog(self))
        await self.add_cog(HeavenPanelCog(self))
        await self.add_cog(DaoConfigCog(self))
        await self.add_cog(DaoBondsCog(self))
        await self.add_cog(SectsCog(self))
        await self.add_cog(ItemsCog(self))
        await self.add_cog(AlchemyCog(self))
        await self.add_cog(ReincarnationCog(self))
        await self.add_cog(SecretRealmsCog(self))
        await self.add_cog(WorldEventsCog(self))
        await self.add_cog(DaoLawsCog(self))
        await self.add_cog(AuctionCog(self))
        await self.add_cog(ReactionRolesCog(self))
        await self.add_cog(TranscendenceCog(self))

        for loop in (self.qi_flush_loop, self.presence_loop,
                     self.backup_loop, self.event_scheduler_loop,
                     self.market_expiry_loop, self.stored_qi_regen_loop):
            if not loop.is_running():
                loop.start()

    async def on_ready(self) -> None:
        if self._started:
            return
        self._started = True
        log.info("Heavenly Dao has awakened in %d guild(s)", len(self.guilds))

        # Instant command sync: copy global commands to every joined guild tree
        if config.DEV_GUILD_ID:
            guild_obj = discord.Object(id=config.DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
            log.info("Synced slash commands instantly to dev guild ID %d", config.DEV_GUILD_ID)

        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            except Exception as e:
                log.warning("Failed to sync commands to guild %s (%d): %s", guild.name, guild.id, e)

        try:
            await self.tree.sync()
            log.info("Synced slash commands globally across all guilds")
        except Exception as e:
            log.warning("Global tree sync warning: %s", e)
        await self._update_presence()

        for guild in self.guilds:
            cfg = await self._guild_config(guild.id)
            channel = guild.get_channel(cfg["system_channel_id"]) if cfg["system_channel_id"] else None
            if channel is not None:
                await self._send_awakening(guild, channel)

    # ------------------------------------------------------------ config helper
    async def _guild_config(self, guild_id: int) -> dict:
        row = await self.db.fetchone(
            "SELECT * FROM guild_config WHERE guild_id=?", (guild_id,)
        )
        if row:
            return dict(row)
        defaults = {
            "guild_id": guild_id,
            "qi_enabled_channels": "[]",
            "qi_disabled_channels": "[]",
            "admin_role_id": None,
            "admin_user_id": None,
            "xianxia_terms_language": "bilingual",
            "erasure_enabled": 1,
            "groq_enabled": 0,
            "system_channel_id": None,
            "broadcast_channel_id": None,
            "dao_role_to_gender": "{}",
            "updated_at": ui.now_str(),
        }
        await self.db.execute(
            "INSERT INTO guild_config (guild_id, qi_enabled_channels, qi_disabled_channels,"
            " xianxia_terms_language, erasure_enabled, groq_enabled, updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (guild_id, "[]", "[]", "bilingual", 1, 0, ui.now_str()),
        )
        return defaults

    async def _announce_channel(self, guild: discord.Guild):
        cfg = await self._guild_config(guild.id)
        channel = None
        if cfg["broadcast_channel_id"]:
            channel = guild.get_channel(cfg["broadcast_channel_id"])
        if channel is None and cfg["system_channel_id"]:
            channel = guild.get_channel(cfg["system_channel_id"])
        return channel

    async def _send_awakening(self, guild: discord.Guild, channel) -> None:
        text = await self.templates.get("startup")
        embed = discord.Embed(
            title="☯ Heavenly Dao Awakens · 天道觉醒",
            description=text,
            color=ui.GOLD,
        )
        embed.add_field(name="Register", value="`/register` to awaken your cultivation", inline=True)
        embed.add_field(name="Cultivate", value="`/cultivate` to absorb 灵力 (spiritual qi)", inline=True)
        embed.add_field(name="Break Through", value="`/breakthrough` when your 丹田 is full", inline=True)
        embed.set_footer(text="Chat to passively gain Qi · 15 messages/hour cap")
        await channel.send(embed=embed)

    async def _update_presence(self) -> None:
        row = await self.db.fetchone("SELECT COUNT(*) AS c FROM cultivators")
        count = row["c"] if row else 0
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"over {len(self.guilds)} realms | {count} cultivators",
        )
        await self.change_presence(activity=activity)

    # ------------------------------------------------------------ background tasks
    @tasks.loop(seconds=config.QI_BUFFER_FLUSH_SECONDS)
    async def qi_flush_loop(self) -> None:
        await self.flush_qi_buffer()

    async def flush_qi_buffer(self) -> None:
        """Merge the in-memory buffer into qi_buffer, cultivators, and stats.

        Kept as a plain method (not just a task) so the pipeline is unit-testable
        and can also be force-flushed early when the buffer grows too large.
        """
        if not self.qi_buffer:
            return
        batch, self.qi_buffer = self.qi_buffer, []
        bucket = ui.now_utc().strftime("%Y-%m-%d %H:00:00")

        try:
            await self.db.executemany(
                "INSERT INTO qi_buffer (cultivator_id, guild_id, qi_amount, source)"
                " VALUES (?,?,?,?)",
                [(b["cid"], b["guild_id"], b["qi"], b["source"]) for b in batch],
            )
            totals: dict[int, int] = defaultdict(int)
            for b in batch:
                totals[b["cid"]] += b["qi"]
            await self.db.executemany(
                "UPDATE cultivators SET qi_current = qi_current + ? WHERE id = ?",
                [(qi, cid) for cid, qi in totals.items()],
            )
            guild_totals: dict[int, tuple[int, int]] = defaultdict(lambda: (0, 0))
            for b in batch:
                msgs, qi = guild_totals[b["guild_id"]]
                guild_totals[b["guild_id"]] = (msgs + 1, qi + b["qi"])
            for guild_id, (msgs, qi) in guild_totals.items():
                await self.db.execute(
                    "INSERT INTO qi_hourly_stats (guild_id, hour_bucket, message_count, qi_total)"
                    " VALUES (?,?,?,?)"
                    " ON CONFLICT(guild_id, hour_bucket) DO UPDATE SET"
                    " message_count = message_count + excluded.message_count,"
                    " qi_total = qi_total + excluded.qi_total",
                    (guild_id, bucket, msgs, qi),
                )
        except Exception:
            log.exception("qi flush failed; %d rows lost", len(batch))

    @tasks.loop(minutes=config.PRESENCE_UPDATE_MINUTES)
    async def presence_loop(self) -> None:
        await self._update_presence()

    @tasks.loop(seconds=config.STORED_QI_REGEN_INTERVAL_SECONDS)
    async def stored_qi_regen_loop(self) -> None:
        await self.tick_stored_qi_regen()

    async def tick_stored_qi_regen(self) -> None:
        """Apply one hour of natural Stored Qi regen to every cultivator.

        Pure per-row math from core/math.py: gain = base regen + capped flat
        bonus, clamped to the effective max (rolled base + future bonuses).
        """
        rows = await self.db.fetchall(
            "SELECT id, stored_qi_current, stored_qi_max, stored_qi_max_bonus,"
            " stored_qi_regen_bonus FROM cultivators"
        )
        updates: list[tuple[int, int]] = []
        for r in rows:
            effective_max = gm.stored_qi_effective_max(
                r["stored_qi_max"], r["stored_qi_max_bonus"]
            )
            gain = gm.stored_qi_regen_per_hour(r["stored_qi_regen_bonus"])
            new_val = min(effective_max, r["stored_qi_current"] + gain)
            if new_val != r["stored_qi_current"]:
                updates.append((new_val, r["id"]))
        if updates:
            try:
                await self.db.executemany(
                    "UPDATE cultivators SET stored_qi_current=? WHERE id=?", updates
                )
            except Exception:
                log.exception("stored Qi regen tick failed; %d rows skipped", len(updates))

    @tasks.loop(hours=config.BACKUP_INTERVAL_HOURS)
    async def backup_loop(self) -> None:
        dest = await backup_database(self.db)
        if dest:
            log.info("Daily backup written to %s", dest)
        # Best-effort off-server mirror (needs GITHUB_BACKUP_* in .env; skipped otherwise).
        try:
            from scripts import github_backup as gh_backup

            message = await gh_backup.run_mirror()
            log.info("GitHub backup mirror: %s", message)
        except Exception:
            log.exception("GitHub backup mirror failed")

    @tasks.loop(seconds=config.MARKET_EXPIRY_POLL_SECONDS)
    async def market_expiry_loop(self) -> None:
        await self.sweep_expired_listings()

    async def sweep_expired_listings(self) -> None:
        """Expire due auction listings: refund escrowed bids and return items.

        Runs on a fixed cadence (not a command), so it is safe to call directly
        in tests. Each listing is claimed atomically (guarded UPDATE + rowcount)
        so a concurrent `/buy` or `/cancel_listing` cannot double-refund.
        """
        due = await self.db.fetchall(
            "SELECT * FROM market_listings WHERE status='active' AND expires_at <= ?",
            (ui.now_str(),),
        )
        for lst in [dict(r) for r in due]:
            # Atomic claim — only expire if still active.
            cursor = await self.db.execute(
                "UPDATE market_listings SET status='expired', sold_at=? WHERE id=? AND status='active'",
                (ui.now_str(), lst["id"]),
            )
            if not cursor.rowcount:
                continue  # already sold/cancelled by a concurrent operation

            # Refund escrowed bid (if any) to the current bidder.
            if lst["current_bid"] > 0 and lst.get("current_bidder_id"):
                await self.db.execute(
                    "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?",
                    (lst["current_bid"], lst["current_bidder_id"]),
                )

            # Return the item to the seller's inventory.
            await self.db.execute(
                "UPDATE items SET owner_id=? WHERE id=?", (lst["seller_id"], lst["item_id"])
            )

    @tasks.loop(seconds=config.WORLD_EVENT_POLL_SECONDS)
    async def event_scheduler_loop(self) -> None:
        due = await self.db.fetchall(
            "SELECT * FROM world_events WHERE status='pending' AND scheduled_at <= ?",
            (ui.now_str(),),
        )
        for event in due:
            await self.db.execute(
                "UPDATE world_events SET status='active' WHERE id=?", (event["id"],)
            )
            guild = self.get_guild(event["guild_id"])
            if guild is None:
                continue
            channel = await self._announce_channel(guild)
            if channel is None:
                continue
            text = await self.templates.get("world_event", name=event["event_type"])
            embed = discord.Embed(
                title=f"⚡ Heavenly Calamity · {event['event_type'].replace('_', ' ').title()}",
                description=text,
                color=ui.CRIMSON,
            )
            embed.add_field(name="Status", value="Active · 进行中", inline=True)
            await channel.send(embed=embed)

    # Loops that touch Discord API (presence) or need the guild cache
    # (event announcements) wait for the gateway before their first run.
    # (Defined after the loops — class bodies execute top-down.)
    @presence_loop.before_loop
    async def _before_presence(self) -> None:
        await self.wait_until_ready()

    @event_scheduler_loop.before_loop
    async def _before_scheduler(self) -> None:
        await self.wait_until_ready()

    @qi_flush_loop.before_loop
    async def _before_flush(self) -> None:
        await self.wait_until_ready()

    @backup_loop.before_loop
    async def _before_backup(self) -> None:
        await self.wait_until_ready()

    @stored_qi_regen_loop.before_loop
    async def _before_stored_qi_regen(self) -> None:
        await self.wait_until_ready()

    @market_expiry_loop.before_loop
    async def _before_market_expiry(self) -> None:
        await self.wait_until_ready()

    # Small helpers used by cogs ----------------------------------------------
    async def add_flag(self, guild_id: int, user_id: int, flag_type: str, reason: str) -> None:
        await anti_cheat.flag(self.db, guild_id, user_id, flag_type, reason)
