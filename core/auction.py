"""Deterministic Auction House and P2P Trading engine.

Pure Python logic for listing fees, sale taxes, bid increments, active limits,
and listing expiry logic — no Discord or DB dependencies.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


def calculate_listing_fee(price: int, fee_percent: float = 0.05) -> int:
    """Calculate upfront listing fee (default 5% rounded up, min 1 stone)."""
    if price <= 0:
        return 1
    return max(1, math.ceil(price * fee_percent))


def calculate_sale_proceeds(price: int, tax_percent: float = 0.05) -> int:
    """Calculate net spirit stones credited to seller after market tax (default 5%)."""
    if price <= 0:
        return 0
    tax = math.floor(price * tax_percent)
    return max(0, price - tax)


def validate_bid(
    current_bid: int,
    starting_price: int,
    bid_amount: int,
    min_increment_percent: float = 0.10,
) -> Tuple[bool, Optional[str]]:
    """Validate if a bid amount satisfies starting price or 10% minimum increment over current bid."""
    if bid_amount <= 0:
        return False, "Bid amount must be greater than 0 spirit stones."

    if current_bid <= 0:
        if bid_amount < starting_price:
            return False, f"First bid must be at least the starting price of {starting_price:,} spirit stones."
        return True, None

    min_required = current_bid + max(1, math.ceil(current_bid * min_increment_percent))
    if bid_amount < min_required:
        return False, f"Bid must be at least {min_required:,} spirit stones (+10% over current bid of {current_bid:,})."

    return True, None


def can_create_listing(active_listings_count: int, max_listings: int = 5) -> Tuple[bool, Optional[str]]:
    """Validate if a player can open a new market listing (max 5 active)."""
    if active_listings_count >= max_listings:
        return False, f"You have reached the maximum limit of {max_listings} active market listings."
    return True, None


def clamp_listing_duration(hours: int, min_hours: int = 1, max_hours: int = 168) -> int:
    """Clamp a listing duration to the legal window (default 1h to 7 days)."""
    try:
        hours = int(hours)
    except (TypeError, ValueError):
        hours = 24
    return max(min_hours, min(max_hours, hours))


def validate_cancel_listing(listing: Dict[str, Any], seller_id: int) -> Tuple[bool, Optional[str]]:
    """Validate a seller can cancel an active market listing.

    Returns (ok, error). The listing must be active and owned by the caller.
    """
    if not listing:
        return False, "Listing not found."
    if listing.get("status") != "active":
        return False, "This listing is no longer active."
    if listing.get("seller_id") != seller_id:
        return False, "You can only cancel your own market listings."
    return True, None


def process_expired_listings(listings: List[Dict[str, Any]], now_iso: str) -> List[Dict[str, Any]]:
    """Identify and mark market listings that have passed their expiration timestamp."""
    expired = []
    for lst in listings:
        if lst.get("status") == "active" and lst.get("expires_at") and lst["expires_at"] <= now_iso:
            updated = dict(lst)
            updated["status"] = "expired"
            expired.append(updated)
    return expired
