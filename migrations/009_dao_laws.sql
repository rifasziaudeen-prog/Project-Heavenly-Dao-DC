-- ============================================================================
-- Heavenly Dao Engine — migration 009: Dao Laws Endgame System
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Fundamental Laws Catalog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dao_laws (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT    NOT NULL UNIQUE,
    name_zh                TEXT    NOT NULL,
    law_tier               INTEGER DEFAULT 1 CHECK (law_tier BETWEEN 1 AND 5),
    comprehension_required INTEGER NOT NULL DEFAULT 200,
    realm_required         INTEGER NOT NULL DEFAULT 5,
    mastery_effect         TEXT    NOT NULL DEFAULT '{}',
    law_lore               TEXT    NOT NULL,
    created_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Cultivator Law Mastery Junction Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cultivator_laws (
    cultivator_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    law_id                 INTEGER NOT NULL REFERENCES dao_laws(id) ON DELETE CASCADE,
    mastery_percentage     REAL    NOT NULL DEFAULT 0.0 CHECK (mastery_percentage BETWEEN 0.0 AND 100.0),
    insights_gained        INTEGER NOT NULL DEFAULT 0,
    milestone_25_reached   BOOLEAN NOT NULL DEFAULT 0,
    milestone_50_reached   BOOLEAN NOT NULL DEFAULT 0,
    milestone_75_reached   BOOLEAN NOT NULL DEFAULT 0,
    milestone_100_reached  BOOLEAN NOT NULL DEFAULT 0,
    last_enlightenment_at  TEXT,
    PRIMARY KEY (cultivator_id, law_id)
);
CREATE INDEX IF NOT EXISTS idx_cultivator_laws_cultivator
    ON cultivator_laws(cultivator_id, mastery_percentage DESC);

-- Seed initial 5 Fundamental Laws
INSERT OR IGNORE INTO dao_laws (
    name, name_zh, law_tier, comprehension_required, realm_required, mastery_effect, law_lore
) VALUES
(
    'Law of Space', '空间法则', 1, 200, 5,
    '{"25": {"dodge_bonus": 0.10}, "50": {"technique": "Void Step"}, "75": {"movement_bonus": 0.25}, "100": {"teleport": true}}',
    'To comprehend space is to step beyond distance itself. Space folds at the will of the master.'
),
(
    'Law of Time', '时间法则', 1, 300, 5,
    '{"25": {"cooldown_reduction": 0.10}, "50": {"technique": "Temporal Cultivation"}, "75": {"qi_accumulation_bonus": 0.15}, "100": {"rewind_breakthrough": true}}',
    'Time flows like a river. The cultivator who masters it swims against the current.'
),
(
    'Law of Karma', '因果法则', 1, 250, 5,
    '{"25": {"karma_gain_bonus": 0.10}, "50": {"see_auras": true}, "75": {"breakthrough_bonus": 0.20}, "100": {"revive_once": true}}',
    'Every action ripples through eternity. Karma is the unbreakable ledger of the Dao.'
),
(
    'Law of Sword', '剑道法则', 1, 200, 6,
    '{"25": {"damage_bonus": 0.15}, "50": {"passive": "Sword Intent"}, "75": {"crit_rate_bonus": 0.30}, "100": {"execute_sub_20": true}}',
    'The sword is not a weapon. It is the cultivator will made manifest across the heavens.'
),
(
    'Law of Alchemy', '丹道法则', 1, 150, 5,
    '{"25": {"pill_success_bonus": 0.10}, "50": {"cauldron_grade": "Heavenly Flame"}, "75": {"pill_potency_bonus": 0.25}, "100": {"refine_god_grade": true}}',
    'To refine pills is to refine the self. The cauldron is the second dantian.'
);
