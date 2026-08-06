"""Integration tests against a temp DB (no Discord connection required).

  * register -> message Qi -> buffered flush -> stats
  * auction listings -> expiry sweep -> escrow refund + item return
  * /buy atomicity: a crash mid-transaction leaves no partial state, and a
    lost claim race is reported without moving anything
"""
import asyncio
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest

from bot.main import HeavenlyDaoBot
from config import default as config
from core import math as gm
from db import queries as dbq
from db.queries import get_or_create_cultivator
from db.seeds import seed_templates_if_empty
from cogs.auction import AuctionCog


def test_buffered_qi_pipeline_end_to_end():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = HeavenlyDaoBot()
            bot.db.path = str(Path(d) / "test.db")
            await bot.db.connect()
            from db.database import run_migrations

            await run_migrations(bot.db)
            await seed_templates_if_empty(bot.db, config.TEMPLATES_DIR)
            await bot.templates.load()

            row, is_new = await get_or_create_cultivator(bot.db, 555, "Riel", 1)
            assert is_new is True

            gain = gm.calculate_qi_gain(row["realm_tier"], row["comprehension"], source="message")
            bot.qi_buffer.append({"cid": row["id"], "guild_id": 1, "qi": gain, "source": "message"})
            bot.qi_buffer.append({"cid": row["id"], "guild_id": 1, "qi": gain, "source": "message"})
            bot.qi_buffer.append({"cid": row["id"], "guild_id": 1, "qi": gain, "source": "message"})

            await bot.flush_qi_buffer()

            assert bot.qi_buffer == []  # drained
            updated = await bot.db.fetchone(
                "SELECT qi_current FROM cultivators WHERE id=?", (row["id"],)
            )
            assert updated["qi_current"] == gain * 3

            stats = await bot.db.fetchone(
                "SELECT message_count, qi_total FROM qi_hourly_stats WHERE guild_id=1"
            )
            assert stats["message_count"] == 3 and stats["qi_total"] == gain * 3

            logged = await bot.db.fetchone("SELECT COUNT(*) AS c FROM qi_buffer")
            assert logged["c"] == 3  # append-only log intact

            # Second flush with an empty buffer is a no-op
            await bot.flush_qi_buffer()
            assert bot.qi_buffer == []

            await bot.db.close()

    asyncio.run(main())


class _FakeResponse:
    """Stands in for `interaction.response` in cog tests."""

    def __init__(self) -> None:
        self.sent: list = []

    async def send_message(self, *args, **kwargs) -> None:
        self.sent.append((args, kwargs))


class _FakeInteraction:
    def __init__(self, user_id: int) -> None:
        self.user = SimpleNamespace(id=user_id)
        self.guild_id = 1
        self.response = _FakeResponse()


async def _auction_world(bot, temp_path: Path):
    """Migrations + templates + a seller, a buyer, and one live listing."""
    bot.db.path = str(temp_path / "test.db")
    await bot.db.connect()
    from db.database import run_migrations

    await run_migrations(bot.db)
    await seed_templates_if_empty(bot.db, config.TEMPLATES_DIR)
    await bot.templates.load()

    seller, _ = await get_or_create_cultivator(bot.db, 100, "Seller", 1)
    buyer, _ = await get_or_create_cultivator(bot.db, 200, "Buyer", 1)
    await bot.db.execute(
        "UPDATE cultivators SET spirit_stones=? WHERE id=?", (5000, buyer["id"]),
    )
    await bot.db.execute(
        "INSERT INTO items (owner_id, name, item_type, grade) VALUES (?,?,?,?)",
        (seller["id"], "Spirit Sword", "Weapon", "Earth"),
    )
    item = await bot.db.fetchone("SELECT * FROM items WHERE owner_id=?", (seller["id"],))
    cursor = await bot.db.execute(
        "INSERT INTO market_listings (seller_id, item_id, quantity, price, buyout_price,"
        " status, expires_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (seller["id"], item["id"], 1, 1000, 1000, "active", "2999-01-01 00:00:00"),
    )
    return {"seller": seller, "buyer": buyer, "item": item, "listing_id": cursor.lastrowid}


def test_buy_completes_atomically_when_all_is_well():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = HeavenlyDaoBot()
            try:
                world = await _auction_world(bot, Path(d))
                cog = AuctionCog(bot)
                buyer = world["buyer"]

                await cog.buy.callback(cog, _FakeInteraction(200), world["listing_id"])

                lst = await bot.db.fetchone(
                    "SELECT * FROM market_listings WHERE id=?", (world["listing_id"],)
                )
                assert lst["status"] == "sold"
                buyer_row = await bot.db.fetchone(
                    "SELECT * FROM cultivators WHERE id=?", (buyer["id"],)
                )
                assert buyer_row["spirit_stones"] == 4000     # 5000 - 1000
                seller_row = await bot.db.fetchone(
                    "SELECT * FROM cultivators WHERE id=?", (world["seller"]["id"],)
                )
                assert seller_row["spirit_stones"] == 950      # 1000 - 5% tax
                item = await bot.db.fetchone(
                    "SELECT * FROM items WHERE id=?", (world["item"]["id"],)
                )
                assert item["owner_id"] == buyer["id"]
            finally:
                await bot.db.close()

    asyncio.run(main())


def test_buy_crash_mid_transaction_leaves_no_partial_state(monkeypatch):
    """Simulate the process dying between the claim and the item transfer:
    the listing must stay active and NO stones may move."""
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = HeavenlyDaoBot()
            try:
                world = await _auction_world(bot, Path(d))
                cog = AuctionCog(bot)
                buyer = world["buyer"]
                buyer_before = (await bot.db.fetchone(
                    "SELECT spirit_stones FROM cultivators WHERE id=?", (buyer["id"],)
                ))["spirit_stones"]
                seller_before = (await bot.db.fetchone(
                    "SELECT spirit_stones FROM cultivators WHERE id=?", (world["seller"]["id"],)
                ))["spirit_stones"]

                real_execute = bot.db.execute

                async def crash_at_item_transfer(sql: str, params: tuple = ()):
                    # The item hand-off is the LAST write of the buy sequence —
                    # dying there means claim + payments already happened
                    # inside the transaction, which must all roll back.
                    if "UPDATE items SET owner_id=" in sql:
                        raise RuntimeError("simulated process crash")
                    return await real_execute(sql, params)

                monkeypatch.setattr(bot.db, "execute", crash_at_item_transfer)

                with pytest.raises(RuntimeError):
                    await cog.buy.callback(cog, _FakeInteraction(200), world["listing_id"])

                # No partial state: listing still active, nobody charged or
                # paid, item still with its original owner.
                lst = await bot.db.fetchone(
                    "SELECT * FROM market_listings WHERE id=?", (world["listing_id"],)
                )
                assert lst["status"] == "active"
                buyer_row = await bot.db.fetchone(
                    "SELECT spirit_stones FROM cultivators WHERE id=?", (buyer["id"],)
                )
                seller_row = await bot.db.fetchone(
                    "SELECT spirit_stones FROM cultivators WHERE id=?", (world["seller"]["id"],)
                )
                assert buyer_row["spirit_stones"] == buyer_before
                assert seller_row["spirit_stones"] == seller_before
                item = await bot.db.fetchone(
                    "SELECT owner_id FROM items WHERE id=?", (world["item"]["id"],)
                )
                assert item["owner_id"] == world["seller"]["id"]
            finally:
                await bot.db.close()

    asyncio.run(main())


def test_buy_lost_claim_race_is_reported_and_moves_nothing(monkeypatch):
    """A concurrent sale flips the listing between the read and the guarded
    claim — the buyer must be told and nothing may change."""
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = HeavenlyDaoBot()
            try:
                world = await _auction_world(bot, Path(d))
                cog = AuctionCog(bot)
                buyer = world["buyer"]

                # The listing is actually already sold on disk, but the lookup
                # (as if stale) still reports it active -> validation passes,
                # the guarded claim matches 0 rows, ListingNotActive fires.
                await bot.db.execute(
                    "UPDATE market_listings SET status='sold' WHERE id=?",
                    (world["listing_id"],),
                )
                real_lookup = dbq.market_listing_by_id

                async def stale_lookup(db, listing_id: int):
                    row = await real_lookup(db, listing_id)
                    stale = dict(row)
                    stale["status"] = "active"
                    return stale

                monkeypatch.setattr(dbq, "market_listing_by_id", stale_lookup)

                interaction = _FakeInteraction(200)
                await cog.buy.callback(cog, interaction, world["listing_id"])

                assert interaction.response.sent  # user was told
                msg = interaction.response.sent[0][0][0]          # positional text
                assert "already sold" in msg
                buyer_row = await bot.db.fetchone(
                    "SELECT spirit_stones FROM cultivators WHERE id=?", (buyer["id"],)
                )
                assert buyer_row["spirit_stones"] == 5000       # never charged
                item = await bot.db.fetchone(
                    "SELECT owner_id FROM items WHERE id=?", (world["item"]["id"],)
                )
                assert item["owner_id"] == world["seller"]["id"]  # never moved
            finally:
                await bot.db.close()

    asyncio.run(main())


def test_expiry_sweep_crash_mid_listing_keeps_everything_active(monkeypatch):
    """Dying between 'mark expired' and 'return the item' must roll the whole
    listing back — the bidder isn't refunded and the item stays listed."""
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = HeavenlyDaoBot()
            try:
                world = await _auction_world(bot, Path(d))
                seller, buyer = world["seller"], world["buyer"]
                # A standing bid, past its expiry.
                await bot.db.execute(
                    "UPDATE market_listings SET current_bid=?, current_bidder_id=?,"
                    " expires_at=? WHERE id=?",
                    (800, buyer["id"], "2000-01-01 00:00:00", world["listing_id"]),
                )
                bidder_before = (await bot.db.fetchone(
                    "SELECT spirit_stones FROM cultivators WHERE id=?", (buyer["id"],)
                ))["spirit_stones"]

                real_execute = bot.db.execute

                async def crash_at_item_return(sql: str, params: tuple = ()):
                    if "UPDATE items SET owner_id=" in sql:
                        raise RuntimeError("simulated process crash")
                    return await real_execute(sql, params)

                monkeypatch.setattr(bot.db, "execute", crash_at_item_return)

                with pytest.raises(RuntimeError):
                    await bot.sweep_expired_listings()

                # The whole listing rolled back: still active, no refund.
                lst = await bot.db.fetchone(
                    "SELECT * FROM market_listings WHERE id=?", (world["listing_id"],)
                )
                assert lst["status"] == "active"
                assert lst["current_bid"] == 800
                bidder_row = await bot.db.fetchone(
                    "SELECT spirit_stones FROM cultivators WHERE id=?", (buyer["id"],)
                )
                assert bidder_row["spirit_stones"] == bidder_before
                item = await bot.db.fetchone(
                    "SELECT owner_id FROM items WHERE id=?", (world["item"]["id"],)
                )
                assert item["owner_id"] == seller["id"]   # not returned/not moved
            finally:
                await bot.db.close()

    asyncio.run(main())


def test_expiry_sweep_refunds_escrow_and_returns_item():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bot = HeavenlyDaoBot()
            bot.db.path = str(Path(d) / "test.db")
            await bot.db.connect()
            from db.database import run_migrations

            await run_migrations(bot.db)
            await seed_templates_if_empty(bot.db, config.TEMPLATES_DIR)
            await bot.templates.load()

            # Seller + bidder + an item put up for sale.
            seller, _ = await get_or_create_cultivator(bot.db, 100, "Seller", 1)
            bidder, _ = await get_or_create_cultivator(bot.db, 200, "Bidder", 1)
            await bot.db.execute(
                "INSERT INTO items (owner_id, name, item_type, grade) VALUES (?,?,?,?)",
                (seller["id"], "Spirit Sword", "Weapon", "Earth"),
            )
            item = await bot.db.fetchone("SELECT * FROM items WHERE owner_id=?", (seller["id"],))

            # Listing already past its expiry, with a standing bid.
            cursor = await bot.db.execute(
                "INSERT INTO market_listings (seller_id, item_id, quantity, price, buyout_price,"
                " current_bid, current_bidder_id, status, expires_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (seller["id"], item["id"], 1, 1000, None, 800, bidder["id"], "active", "2000-01-01 00:00:00"),
            )
            listing_id = cursor.lastrowid

            await bot.sweep_expired_listings()

            # Listing marked expired; escrow refunded to bidder; item back to seller.
            lst = await bot.db.fetchone("SELECT * FROM market_listings WHERE id=?", (listing_id,))
            assert lst["status"] == "expired"
            bidder_row = await bot.db.fetchone("SELECT * FROM cultivators WHERE id=?", (bidder["id"],))
            assert bidder_row["spirit_stones"] == 800
            item_row = await bot.db.fetchone("SELECT * FROM items WHERE id=?", (item["id"],))
            assert item_row["owner_id"] == seller["id"]

            # Second sweep is a no-op (listing already expired).
            await bot.sweep_expired_listings()
            lst2 = await bot.db.fetchone("SELECT * FROM market_listings WHERE id=?", (listing_id,))
            assert lst2["status"] == "expired"
            bidder_row2 = await bot.db.fetchone("SELECT * FROM cultivators WHERE id=?", (bidder["id"],))
            assert bidder_row2["spirit_stones"] == 800  # not double-refunded

            await bot.db.close()

    asyncio.run(main())
