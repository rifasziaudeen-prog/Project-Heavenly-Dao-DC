"""Integration tests against a temp DB (no Discord connection required).

  * register -> message Qi -> buffered flush -> stats
  * auction listings -> expiry sweep -> escrow refund + item return
"""
import asyncio
import tempfile
from pathlib import Path

from bot.main import HeavenlyDaoBot
from config import default as config
from core import math as gm
from db.queries import get_or_create_cultivator
from db.seeds import seed_templates_if_empty


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
