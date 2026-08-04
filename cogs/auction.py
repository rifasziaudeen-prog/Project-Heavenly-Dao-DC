"""Auction House & P2P Trading Cog — /market, /sell, /buy, /bid, /my_listings, /cancel_listing, /trade, /trade_accept, /trade_decline."""
from __future__ import annotations

import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import auction as core_auc
from db import queries


class AuctionCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _cultivator(self, guild_id: int, user_id: int):
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        return dict(row) if row else None

    # ================================================================= /market
    @app_commands.command(
        name="market",
        description="Browse active market listings in the Heavenly Auction House",
    )
    async def market(self, interaction: discord.Interaction) -> None:
        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        listings = await queries.active_market_listings(self.bot.db)

        if not listings:
            embed = discord.Embed(
                title=ui.format_title("Heavenly Auction House · 天宝阁", lang),
                description="The market stalls are currently empty. List an item using `/sell`!",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=ui.format_title("🏪 Heavenly Auction House · 天宝阁", lang),
            description="Player-driven market — Buy, bid, or list rare spiritual treasures!",
            color=ui.GOLD,
        )

        for lst in listings[:10]:
            bid_str = f"{lst['current_bid']:,} stones" if lst['current_bid'] > 0 else "No Bids"
            buyout_str = f"{lst['buyout_price']:,} stones" if lst.get('buyout_price') else "No Buyout"

            embed.add_field(
                name=f"Listing #{lst['id']} — {lst['quantity']}x {lst['item_name']} ({lst['grade']})",
                value=(
                    f"**Seller**: {lst['seller_name']}\n"
                    f"**Starting Price**: {lst['price']:,} stones | **Top Bid**: {bid_str}\n"
                    f"**Instant Buyout**: {buyout_str} | **Expires**: {lst['expires_at'][:16]}"
                ),
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ======================================================== /my_listings
    @app_commands.command(
        name="my_listings",
        description="View your active market listings and top bids",
    )
    async def my_listings(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        listings = await queries.active_listings_by_seller(self.bot.db, row["id"])

        if not listings:
            embed = discord.Embed(
                title=ui.format_title("📜 Your Market Listings · 我的上架", lang),
                description="You have no active market listings. List an item with `/sell`!",
                color=ui.CYAN,
            )
            embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=ui.format_title(f"📜 Your Market Listings · 我的上架 ({len(listings)})", lang),
            description="Your active listings — cancel any of them with `/cancel_listing`.",
            color=ui.GOLD,
        )

        for lst in listings[:10]:
            bid_str = f"{lst['current_bid']:,} stones" if lst['current_bid'] > 0 else "No Bids"
            buyout_str = f"{lst['buyout_price']:,} stones" if lst.get('buyout_price') else "No Buyout"

            embed.add_field(
                name=f"Listing #{lst['id']} — {lst['quantity']}x {lst['item_name']} ({lst['grade']})",
                value=(
                    f"**Starting Price**: {lst['price']:,} stones | **Top Bid**: {bid_str}\n"
                    f"**Instant Buyout**: {buyout_str} | **Expires**: {lst['expires_at'][:16]}"
                ),
                inline=False,
            )

        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # =================================================================== /sell
    @app_commands.command(
        name="sell",
        description="List an item for sale on the market (5% listing fee)",
    )
    async def sell(
        self,
        interaction: discord.Interaction,
        item_name: str,
        price: int,
        duration_hours: int = 24,
        buyout_price: int = None,
    ) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        # Active listing limit check
        active_lsts = await queries.active_listings_by_seller(self.bot.db, row["id"])
        can_list, limit_err = core_auc.can_create_listing(len(active_lsts))
        if not can_list:
            await interaction.response.send_message(limit_err, ephemeral=True)
            return

        # Check item ownership
        item_row = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) LIMIT 1",
            (row["id"], item_name.strip()),
        )
        if not item_row:
            await interaction.response.send_message(f"You do not own an item named **{item_name}**.", ephemeral=True)
            return
        item_dict = dict(item_row)

        if item_dict.get("is_equipped"):
            await interaction.response.send_message("Cannot list an equipped item. Please `/equip` another item first.", ephemeral=True)
            return

        fee = core_auc.calculate_listing_fee(price)
        if row["spirit_stones"] < fee:
            await interaction.response.send_message(f"Insufficient spirit stones for the listing fee ({fee:,} stones required).", ephemeral=True)
            return

        # Deduct listing fee & remove item from active inventory
        await self.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones-? WHERE id=?",
            (fee, row["id"]),
        )

        # Set item owner to null while listed
        await self.bot.db.execute("UPDATE items SET owner_id=NULL WHERE id=?", (item_dict["id"],))

        duration_hours = core_auc.clamp_listing_duration(duration_hours)
        expires_at = ui.future_str(hours=duration_hours)

        cursor = await self.bot.db.execute(
            "INSERT INTO market_listings (seller_id, item_id, quantity, price, buyout_price, expires_at)"
            " VALUES (?,?,?,?,?,?)",
            (row["id"], item_dict["id"], item_dict.get("quantity", 1), price, buyout_price, expires_at),
        )
        listing_id = cursor.lastrowid

        embed = discord.Embed(
            title=ui.format_title(f"📦 Item Listed: Listing #{listing_id} · 上架", lang),
            description=(
                f"**{item_dict['name']}** has been listed on the market!\n"
                f"**Starting Price**: {price:,} Spirit Stones\n"
                + (f"**Buyout Price**: {buyout_price:,} Spirit Stones\n" if buyout_price else "")
                + f"**Listing Fee Paid**: {fee:,} Spirit Stones\n"
                + f"**Listing Duration**: {duration_hours}h (expires {expires_at[:16]})"
            ),
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ==================================================================== /buy
    @app_commands.command(
        name="buy",
        description="Instant buy an item from the market at listed price/buyout",
    )
    async def buy(self, interaction: discord.Interaction, listing_id: int) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        lst = await queries.market_listing_by_id(self.bot.db, listing_id)
        if not lst or lst["status"] != "active":
            await interaction.response.send_message(f"Listing #{listing_id} is no longer active.", ephemeral=True)
            return

        if lst["seller_id"] == row["id"]:
            await interaction.response.send_message("You cannot buy your own market listing!", ephemeral=True)
            return

        cost = lst["buyout_price"] if lst.get("buyout_price") else lst["price"]
        if row["spirit_stones"] < cost:
            await interaction.response.send_message(f"Insufficient spirit stones ({cost:,} required, you have {row['spirit_stones']:,}).", ephemeral=True)
            return

        proceeds = core_auc.calculate_sale_proceeds(cost)

        # Atomic claim — only sell if the listing is still active. Guards against
        # a concurrent sweep_expired_listings / cancel_listing racing this buy.
        cursor = await self.bot.db.execute(
            "UPDATE market_listings SET status='sold', sold_at=? WHERE id=? AND status='active'",
            (ui.now_str(), listing_id),
        )
        if not cursor.rowcount:
            await interaction.response.send_message(
                f"Listing #{listing_id} was already sold, cancelled, or expired.", ephemeral=True
            )
            return

        # Deduct buyer stones
        await self.bot.db.execute("UPDATE cultivators SET spirit_stones=spirit_stones-? WHERE id=?", (cost, row["id"]))

        # Credit seller proceeds
        await self.bot.db.execute("UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?", (proceeds, lst["seller_id"]))

        # Refund previous bidder if any
        if lst.get("current_bidder_id") and lst["current_bid"] > 0:
            await self.bot.db.execute("UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?", (lst["current_bid"], lst["current_bidder_id"]))

        # Transfer item to buyer
        await self.bot.db.execute("UPDATE items SET owner_id=? WHERE id=?", (row["id"], lst["item_id"]))

        embed = discord.Embed(
            title=ui.format_title(f"🎉 Item Purchased: Listing #{listing_id} · 交易成功", lang),
            description=(
                f"You purchased **{lst['quantity']}x {lst['item_name']}** for **{cost:,} Spirit Stones**!\n"
                f"The item has been added to your `/inventory`."
            ),
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ==================================================================== /bid
    @app_commands.command(
        name="bid",
        description="Place a bid on an active auction listing (min +10% over current bid)",
    )
    async def bid(self, interaction: discord.Interaction, listing_id: int, amount: int) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        lst = await queries.market_listing_by_id(self.bot.db, listing_id)
        if not lst or lst["status"] != "active":
            await interaction.response.send_message(f"Listing #{listing_id} is no longer active.", ephemeral=True)
            return

        if lst["seller_id"] == row["id"]:
            await interaction.response.send_message("You cannot bid on your own market listing!", ephemeral=True)
            return

        valid, err = core_auc.validate_bid(lst["current_bid"], lst["price"], amount)
        if not valid:
            await interaction.response.send_message(err, ephemeral=True)
            return

        if row["spirit_stones"] < amount:
            await interaction.response.send_message(f"Insufficient spirit stones to place bid of {amount:,}.", ephemeral=True)
            return

        # Atomic claim — only bid if the listing is still active. Guards against
        # a concurrent sweep/cancel racing this bid (stale escrow refunds).
        cursor = await self.bot.db.execute(
            "UPDATE market_listings SET current_bid=?, current_bidder_id=? WHERE id=? AND status='active'",
            (amount, row["id"], listing_id),
        )
        if not cursor.rowcount:
            await interaction.response.send_message(
                f"Listing #{listing_id} was already sold, cancelled, or expired.", ephemeral=True
            )
            return

        # Deduct new bidder's stones
        await self.bot.db.execute("UPDATE cultivators SET spirit_stones=spirit_stones-? WHERE id=?", (amount, row["id"]))

        # Refund previous bidder if any
        if lst.get("current_bidder_id") and lst["current_bid"] > 0:
            await self.bot.db.execute("UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?", (lst["current_bid"], lst["current_bidder_id"]))

        embed = discord.Embed(
            title=ui.format_title(f"🏷 Bid Placed: Listing #{listing_id} · 竞价", lang),
            description=f"**{row['username']}** placed a top bid of **{amount:,} Spirit Stones** on **{lst['item_name']}**!",
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ===================================================== /cancel_listing
    @app_commands.command(
        name="cancel_listing",
        description="Cancel one of your active listings — refunds fee & returns item",
    )
    async def cancel_listing(self, interaction: discord.Interaction, listing_id: int) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        lst = await queries.market_listing_by_id(self.bot.db, listing_id)
        ok, err = core_auc.validate_cancel_listing(lst, row["id"])
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        # 1. Atomically claim the cancel — guarded UPDATE + rowcount check so a
        #    concurrent /buy (or a crash-retry) cannot double-apply the refunds.
        cursor = await self.bot.db.execute(
            "UPDATE market_listings SET status='cancelled', sold_at=? WHERE id=? AND status='active' AND seller_id=?",
            (ui.now_str(), listing_id, row["id"]),
        )
        if not cursor.rowcount:
            await interaction.response.send_message(
                f"Listing #{listing_id} is no longer active or is not yours.", ephemeral=True
            )
            return

        # 2. Refund escrowed bid (if any) to the current bidder
        if lst.get("current_bid") and lst["current_bid"] > 0 and lst.get("current_bidder_id"):
            await self.bot.db.execute(
                "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?",
                (lst["current_bid"], lst["current_bidder_id"]),
            )

        # 3. Refund the listing fee to the seller
        fee_refund = core_auc.calculate_listing_fee(lst["price"])
        await self.bot.db.execute(
            "UPDATE cultivators SET spirit_stones=spirit_stones+? WHERE id=?",
            (fee_refund, row["id"]),
        )

        # 4. Return the item to the seller's inventory
        await self.bot.db.execute(
            "UPDATE items SET owner_id=? WHERE id=?", (row["id"], lst["item_id"])
        )

        embed = discord.Embed(
            title=ui.format_title(f"🗑 Listing Cancelled: Listing #{listing_id} · 下架", lang),
            description=(
                f"**{lst['quantity']}x {lst['item_name']}** has been returned to your `/inventory`.\n"
                f"**Listing Fee Refunded**: {fee_refund:,} Spirit Stones\n"
                + (f"**Bid Refunded**: {lst['current_bid']:,} Spirit Stones to the top bidder\n" if lst["current_bid"] > 0 else "")
                + "The item is no longer listed on the market."
            ),
            color=ui.CRIMSON,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ============================================================= /trade
    @app_commands.command(
        name="trade",
        description="Offer a direct item trade to another cultivator",
    )
    async def trade(
        self,
        interaction: discord.Interaction,
        target_user: discord.User,
        item_name: str,
        quantity: int = 1,
    ) -> None:
        sender = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not sender:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        recipient = await self._cultivator(interaction.guild_id, target_user.id)
        if not recipient:
            await interaction.response.send_message(f"{target_user.display_name} has not registered yet.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        item_row = await self.bot.db.fetchone(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) LIMIT 1",
            (sender["id"], item_name.strip()),
        )
        if not item_row:
            await interaction.response.send_message(f"You do not own **{item_name}**.", ephemeral=True)
            return

        cursor = await self.bot.db.execute(
            "INSERT INTO trade_offers (sender_id, recipient_id, item_id, quantity) VALUES (?,?,?,?)",
            (sender["id"], recipient["id"], item_row["id"], quantity),
        )
        offer_id = cursor.lastrowid

        embed = discord.Embed(
            title=ui.format_title(f"🤝 Trade Offer Sent: Offer #{offer_id} · 交易发函", lang),
            description=(
                f"**{sender['username']}** offered **{quantity}x {item_row['name']}** to **{recipient['username']}**!\n"
                f"**{recipient['username']}**, use `/trade_accept` or `/trade_decline` to respond within 10 minutes."
            ),
            color=ui.CYAN,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ====================================================== /trade_accept
    @app_commands.command(
        name="trade_accept",
        description="Accept your pending trade offer",
    )
    async def trade_accept(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        offer = await queries.pending_trade_offer(self.bot.db, row["id"])
        if not offer:
            await interaction.response.send_message("You have no pending trade offers.", ephemeral=True)
            return

        # Transfer item to recipient
        await self.bot.db.execute("UPDATE items SET owner_id=? WHERE id=?", (row["id"], offer["item_id"]))
        await self.bot.db.execute("UPDATE trade_offers SET status='accepted' WHERE id=?", (offer["id"],))

        embed = discord.Embed(
            title=ui.format_title(f"✅ Trade Accepted: Offer #{offer['id']} · 交易完成", lang),
            description=f"**{row['username']}** accepted the trade! Received **{offer['quantity']}x {offer['item_name']}** from **{offer['sender_name']}**.",
            color=ui.GOLD,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)

    # ====================================================== /trade_decline
    @app_commands.command(
        name="trade_decline",
        description="Decline your pending trade offer",
    )
    async def trade_decline(self, interaction: discord.Interaction) -> None:
        row = await self._cultivator(interaction.guild_id, interaction.user.id)
        if not row:
            await interaction.response.send_message("Please `/register` first.", ephemeral=True)
            return

        cfg = await self.bot._guild_config(interaction.guild_id)
        lang = cfg.get("xianxia_terms_language", "bilingual")

        offer = await queries.pending_trade_offer(self.bot.db, row["id"])
        if not offer:
            await interaction.response.send_message("You have no pending trade offers.", ephemeral=True)
            return

        await self.bot.db.execute("UPDATE trade_offers SET status='declined' WHERE id=?", (offer["id"],))

        embed = discord.Embed(
            title=ui.format_title(f"❌ Trade Declined: Offer #{offer['id']} · 交易拒绝", lang),
            description=f"**{row['username']}** declined the trade offer from **{offer['sender_name']}**.",
            color=ui.CRIMSON,
        )
        embed.set_footer(text=ui.format_title("Heavenly Dao Engine · 天道引擎", lang))
        await interaction.response.send_message(embed=embed)
