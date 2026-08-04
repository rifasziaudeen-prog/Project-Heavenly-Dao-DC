-- ============================================================================
-- Migration 012: Spiritual Aptitudes & Martial Intent Engine (PostgreSQL 15+)
--
-- Adds multi-stat Spiritual Aptitude Profile to every cultivator.
-- Uses ADD COLUMN IF NOT EXISTS so reruns are safe.
-- ============================================================================

-- ☯ Yin-Yang Balance
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS yin_yang_balance INT NOT NULL DEFAULT 0;

-- 🌀 Five Phases (Wuxing) aptitudes
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS affinity_fire   INT NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS affinity_water  INT NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS affinity_wood   INT NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS affinity_metal  INT NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS affinity_earth  INT NOT NULL DEFAULT 10;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS affinity_qi     INT NOT NULL DEFAULT 10;

-- ⚔️ Martial Weapon Intents
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS intent_sword INT NOT NULL DEFAULT 5;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS intent_sabre INT NOT NULL DEFAULT 5;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS intent_spear INT NOT NULL DEFAULT 5;
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS intent_fist  INT NOT NULL DEFAULT 5;

-- Special Root flag (extensible)
ALTER TABLE cultivators ADD COLUMN IF NOT EXISTS special_root TEXT;
