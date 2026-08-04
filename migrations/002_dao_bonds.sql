-- ============================================================================
-- Heavenly Dao Engine — migration 002: Dao Bonds (player-to-player social core)
--
-- Review v2 pivot: Dao Companions / rivals / masters / disciples are REAL
-- players, not NPCs. The old `companions` table (001) stays for future NPC
-- systems (merchants, realm guardians, lore) but the social fabric moves to
-- `dao_bonds` — a relationship graph between cultivators.
--
-- All rules (gender matrix, realm gaps, polygamy limits, synergy, severance
-- drama) are enforced in `core/dao_bonds.py` — deterministic and auditable.
-- ============================================================================

CREATE TABLE IF NOT EXISTS dao_bonds (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivator_a_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    cultivator_b_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    initiator_id             INTEGER NOT NULL REFERENCES cultivators(id),
    bond_type                TEXT    NOT NULL CHECK (bond_type IN (
                                 'dao_companion',
                                 'sworn_sibling',
                                 'master_disciple',
                                 'rival',
                                 'sect_sibling',
                                 'dual_cultivation_partner')),
    bond_tier                INTEGER NOT NULL DEFAULT 1 CHECK (bond_tier BETWEEN 1 AND 20),
    bond_points              INTEGER NOT NULL DEFAULT 0,
    status                   TEXT    NOT NULL DEFAULT 'forming' CHECK (status IN (
                                 'forming', 'active', 'distant', 'severed', 'ascended', 'rivalry')),
    severed_by               INTEGER,
    severance_reason         TEXT,
    severance_karma_impact   INTEGER NOT NULL DEFAULT 0,
    shared_events            TEXT    NOT NULL DEFAULT '[]',   -- JSON array of shared-history events
    dual_cultivation_count   INTEGER NOT NULL DEFAULT 0,
    last_dual_cultivation_at TEXT,
    formed_at                TEXT    NOT NULL DEFAULT (datetime('now')),
    severed_at               TEXT
);

-- One bond per pair, regardless of direction (review: LEAST/GREATEST -> MIN/MAX)
CREATE UNIQUE INDEX IF NOT EXISTS idx_dao_bonds_pair
    ON dao_bonds(MIN(cultivator_a_id, cultivator_b_id),
                 MAX(cultivator_a_id, cultivator_b_id));
CREATE INDEX IF NOT EXISTS idx_dao_bonds_status_type
    ON dao_bonds(status, bond_type);
CREATE INDEX IF NOT EXISTS idx_dao_bonds_member
    ON dao_bonds(cultivator_a_id, status);
CREATE INDEX IF NOT EXISTS idx_dao_bonds_member_b
    ON dao_bonds(cultivator_b_id, status);

-- Per-guild gender-role mapping for bond formation rules.
-- JSON: {"<discord_role_id>": "male" | "female", ...}
ALTER TABLE guild_config ADD COLUMN dao_role_to_gender TEXT NOT NULL DEFAULT '{}';

-- Rage cultivation buff: victim of a one-sided severance gains +15% breakthrough
-- chance for 7 days ("Betrayed" title).
ALTER TABLE cultivators ADD COLUMN rage_breakthrough_bonus_until TEXT;
