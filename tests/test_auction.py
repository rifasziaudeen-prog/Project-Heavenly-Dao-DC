"""Pure logic unit tests for Auction House & P2P Trading (core/auction.py)."""
from core import auction as core_auc


def test_calculate_listing_fee():
    assert core_auc.calculate_listing_fee(100) == 5
    assert core_auc.calculate_listing_fee(10) == 1
    assert core_auc.calculate_listing_fee(1) == 1
    assert core_auc.calculate_listing_fee(1000) == 50


def test_calculate_sale_proceeds():
    assert core_auc.calculate_sale_proceeds(100) == 95
    assert core_auc.calculate_sale_proceeds(1000) == 950
    assert core_auc.calculate_sale_proceeds(0) == 0


def test_validate_bid_first_bid():
    # Valid first bid equal to starting price
    ok, err = core_auc.validate_bid(current_bid=0, starting_price=100, bid_amount=100)
    assert ok and err is None

    # Invalid first bid below starting price
    ok, err = core_auc.validate_bid(current_bid=0, starting_price=100, bid_amount=90)
    assert not ok and "starting price" in err


def test_validate_bid_increment():
    # Valid bid (+10% over current 100 -> min 110)
    ok, err = core_auc.validate_bid(current_bid=100, starting_price=50, bid_amount=110)
    assert ok and err is None

    # Invalid bid (+5% over current 100 -> 105 fails)
    ok, err = core_auc.validate_bid(current_bid=100, starting_price=50, bid_amount=105)
    assert not ok and "+10%" in err


def test_can_create_listing_limit():
    ok, err = core_auc.can_create_listing(4)
    assert ok and err is None

    ok, err = core_auc.can_create_listing(5)
    assert not ok and "maximum limit" in err


def test_validate_cancel_listing_own_active():
    listing = {"id": 1, "status": "active", "seller_id": 42}
    ok, err = core_auc.validate_cancel_listing(listing, seller_id=42)
    assert ok and err is None


def test_validate_cancel_listing_not_active():
    for status in ("sold", "expired", "cancelled"):
        listing = {"id": 1, "status": status, "seller_id": 42}
        ok, err = core_auc.validate_cancel_listing(listing, seller_id=42)
        assert not ok and "no longer active" in err


def test_validate_cancel_listing_wrong_seller():
    listing = {"id": 1, "status": "active", "seller_id": 42}
    ok, err = core_auc.validate_cancel_listing(listing, seller_id=99)
    assert not ok and "own market listings" in err


def test_validate_cancel_listing_missing():
    ok, err = core_auc.validate_cancel_listing(None, seller_id=42)
    assert not ok and "not found" in err


def test_clamp_listing_duration():
    assert core_auc.clamp_listing_duration(24) == 24
    assert core_auc.clamp_listing_duration(0) == 1
    assert core_auc.clamp_listing_duration(-5) == 1
    assert core_auc.clamp_listing_duration(1000) == 168
    assert core_auc.clamp_listing_duration(None) == 24
    assert core_auc.clamp_listing_duration("abc") == 24


def test_process_expired_listings():
    listings = [
        {"id": 1, "status": "active", "expires_at": "2026-08-04T10:00:00"},
        {"id": 2, "status": "active", "expires_at": "2026-08-04T12:00:00"},
    ]
    expired = core_auc.process_expired_listings(listings, now_iso="2026-08-04T11:00:00")
    assert len(expired) == 1
    assert expired[0]["id"] == 1
    assert expired[0]["status"] == "expired"
