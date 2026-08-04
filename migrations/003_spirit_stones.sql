-- ============================================================================
-- Heavenly Dao Engine — migration 003: spirit stones (sect economy)
--
-- Adds a personal spirit-stone wallet to cultivators so members can donate to
-- their sect treasury and fund array upgrades.  Stones are earned through
-- breakthroughs (+10 per success) and future sources (daily login, events).
-- ============================================================================

ALTER TABLE cultivators ADD COLUMN spirit_stones INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_cultivators_spirit_stones
    ON cultivators(guild_id, spirit_stones DESC);
