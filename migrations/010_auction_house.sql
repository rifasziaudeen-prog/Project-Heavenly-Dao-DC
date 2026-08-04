-- ============================================================================
-- Heavenly Dao Engine — migration 010: Auction House & P2P Trading System
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Market Listings Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_listings (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id              INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    item_id                INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity               INTEGER NOT NULL DEFAULT 1,
    price                  INTEGER NOT NULL, -- Starting price or list price in spirit stones
    buyout_price           INTEGER,          -- Optional instant buy price
    current_bid            INTEGER NOT NULL DEFAULT 0,
    current_bidder_id      INTEGER REFERENCES cultivators(id) ON DELETE SET NULL,
    status                 TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'sold', 'expired', 'cancelled')),
    listed_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at             TEXT    NOT NULL,
    sold_at                TEXT
);
CREATE INDEX IF NOT EXISTS idx_market_listings_status
    ON market_listings(status);
CREATE INDEX IF NOT EXISTS idx_market_listings_seller
    ON market_listings(seller_id, status);

-- ---------------------------------------------------------------------------
-- Direct Trade Offers Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_offers (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id              INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    recipient_id           INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    item_id                INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity               INTEGER NOT NULL DEFAULT 1,
    status                 TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    created_at             TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at             TEXT    NOT NULL DEFAULT (datetime('now', '+10 minutes'))
);
CREATE INDEX IF NOT EXISTS idx_trade_offers_recipient
    ON trade_offers(recipient_id, status);
