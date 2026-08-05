-- ============================================================================
-- Heavenly Dao Engine — migration 015: Stored Qi (存灵气) all-rounder pool
-- ============================================================================

-- Stored Qi is a second resource pool (separate from dantian Qi), spent on
-- techniques / artifacts / laws and restored slowly over time or via pills.
--   stored_qi_current   — current pool
--   stored_qi_max       — randomized awakening max (100-300, +50 Chaos Root)
--   stored_qi_max_bonus — flat bonus from future systems (Heaven Chosen,
--                         passives); effective max = stored_qi_max + bonus
--   stored_qi_regen_bonus — flat extra regen/h from pills/passives/techniques
ALTER TABLE cultivators ADD COLUMN stored_qi_current INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cultivators ADD COLUMN stored_qi_max INTEGER NOT NULL DEFAULT 100;
ALTER TABLE cultivators ADD COLUMN stored_qi_max_bonus INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cultivators ADD COLUMN stored_qi_regen_bonus INTEGER NOT NULL DEFAULT 0;

-- Deterministic backfill for existing cultivators: spread 100-300 by row id.
-- The guard keeps already-rolled rows untouched on a re-run.
UPDATE cultivators SET stored_qi_max = 100 + (id % 201) WHERE stored_qi_max = 100;

-- Existing Chaos Five-Element Roots keep their awakening promise (+50).
UPDATE cultivators SET stored_qi_max = stored_qi_max + 50 WHERE special_root = 'chaos';

-- ---------------------------------------------------------------------------
-- Stored Qi pills (instant restore; higher grades restore more)
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO item_templates (name, item_type, grade, description, effect_data) VALUES
('Stored Qi Elixir', 'Pill', 'Mortal', 'A mild elixir that refills the Stored Qi pool. Instantly restores 30 Stored Qi.', '{"type": "stored_qi_restore", "amount": 30}'),
('Stored Qi Concentrate', 'Pill', 'Earth', 'A potent concentrate distilled from spirit dew. Instantly restores 80 Stored Qi.', '{"type": "stored_qi_restore", "amount": 80}'),
('Stored Qi Heavenly Dew', 'Pill', 'Heaven', 'Dew gathered at dawn from the Celestial Lake. Instantly restores 200 Stored Qi.', '{"type": "stored_qi_restore", "amount": 200}');
