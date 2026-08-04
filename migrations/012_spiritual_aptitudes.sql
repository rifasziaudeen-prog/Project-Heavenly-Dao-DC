-- ============================================================================
-- Migration 012: Spiritual Aptitudes & Martial Intent Engine (SQLite)
--
-- Adds multi-stat Spiritual Aptitude Profile to every cultivator:
--   * Yin-Yang Balance (阴阳) — -100 (Pure Yin) to +100 (Pure Yang)
--   * Five Phases / Wuxing (五行) — Fire, Water, Wood, Metal, Earth, Qi
--   * Martial Weapon Intents (武道真意) — Sword, Sabre, Spear, Fist
--
-- NOTE: Artifact Spirits (器灵) are deferred to a future migration.
-- NOTE: SQLite's ALTER TABLE does not support IF NOT EXISTS —
--       the migration runner in db/database.py already tolerates
--       "duplicate column name" errors, so reruns are safe.
-- ============================================================================

-- ☯ Yin-Yang Balance
ALTER TABLE cultivators ADD COLUMN yin_yang_balance INTEGER NOT NULL DEFAULT 0;

-- 🌀 Five Phases (Wuxing) aptitudes — base 10, max 100
ALTER TABLE cultivators ADD COLUMN affinity_fire   INTEGER NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN affinity_water  INTEGER NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN affinity_wood   INTEGER NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN affinity_metal  INTEGER NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN affinity_earth  INTEGER NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN affinity_qi     INTEGER NOT NULL DEFAULT 10;

-- ⚔️ Martial Weapon Intents — base 5, max 100
ALTER TABLE cultivators ADD COLUMN intent_sword INTEGER NOT NULL DEFAULT 5;
ALTER TABLE cultivators ADD COLUMN intent_sabre INTEGER NOT NULL DEFAULT 5;
ALTER TABLE cultivators ADD COLUMN intent_spear INTEGER NOT NULL DEFAULT 5;
ALTER TABLE cultivators ADD COLUMN intent_fist  INTEGER NOT NULL DEFAULT 5;

-- Special Root flag: NULL = no special root, 'chaos' = Chaos Five-Element Root
-- Designed to be extended (e.g. 'heavenly_fire', 'yin_phantom') in future migrations.
ALTER TABLE cultivators ADD COLUMN special_root TEXT;
