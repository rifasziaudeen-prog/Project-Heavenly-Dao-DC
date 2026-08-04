-- ============================================================================
-- Heavenly Dao Engine — migration 006: Reincarnation System ("Death Is Not The End")
-- ============================================================================

-- Add reincarnation tracking columns to cultivators table
ALTER TABLE cultivators ADD COLUMN inherited_technique TEXT;
ALTER TABLE cultivators ADD COLUMN reincarnation_breakthrough_bonus REAL NOT NULL DEFAULT 0.0;

-- ---------------------------------------------------------------------------
-- Reincarnation Log Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reincarnation_log (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivator_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    cycle_from             INTEGER NOT NULL,
    cycle_to               INTEGER NOT NULL,
    reason                 TEXT    NOT NULL,  -- 'voluntary' / 'erasure' / 'soul_sever'
    realm_tier_at_death    INTEGER NOT NULL,
    realm_sub_stage_at_death INTEGER NOT NULL DEFAULT 1,
    comprehension_retained INTEGER NOT NULL DEFAULT 0,
    luck_retained          INTEGER NOT NULL DEFAULT 0,
    technique_retained     TEXT,
    epitaph                TEXT    NOT NULL,
    created_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reincarnation_log_cultivator
    ON reincarnation_log(cultivator_id, created_at);
