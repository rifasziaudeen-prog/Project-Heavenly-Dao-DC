-- ============================================================================
-- Heavenly Dao Engine — migration 005: Alchemy System & Recipes
-- ============================================================================

-- Add Alchemy columns to cultivators table
ALTER TABLE cultivators ADD COLUMN alchemy_mastery INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cultivators ADD COLUMN alchemy_fame INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cultivators ADD COLUMN equipped_cauldron TEXT NOT NULL DEFAULT 'none';

-- ---------------------------------------------------------------------------
-- Alchemy Recipes Catalog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alchemy_recipes (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    name                     TEXT    NOT NULL UNIQUE,
    grade                    TEXT    NOT NULL DEFAULT 'Mortal', -- Mortal/Earth/Heaven/Immortal/God
    required_realm_tier      INTEGER NOT NULL DEFAULT 1,
    required_alchemy_mastery INTEGER NOT NULL DEFAULT 0,
    base_success_rate        REAL    NOT NULL DEFAULT 0.65,
    recipe_difficulty        INTEGER NOT NULL DEFAULT 50,
    ingredients              TEXT    NOT NULL DEFAULT '[]',     -- JSON: [{"item_name": "Spirit Herb", "quantity": 2, "grade_min": "Mortal"}]
    result_pill_name         TEXT    NOT NULL,
    effect_on_success        TEXT    NOT NULL DEFAULT '{}',
    effect_on_failure        TEXT    NOT NULL DEFAULT '{}',
    effect_on_explosion      TEXT    NOT NULL DEFAULT '{}',
    created_at               TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Alchemy Attempts Log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alchemy_attempts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivator_id    INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    recipe_name      TEXT    NOT NULL,
    result           TEXT    NOT NULL,  -- success / failure / explosion / miracle
    final_rate       REAL    NOT NULL,
    fire_score       INTEGER NOT NULL,
    ingredient_score INTEGER NOT NULL,
    sense_score      INTEGER NOT NULL,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alchemy_attempts_cultivator
    ON alchemy_attempts(cultivator_id, created_at);

-- Seed initial alchemy recipes
INSERT OR IGNORE INTO alchemy_recipes (
    name, grade, required_realm_tier, required_alchemy_mastery,
    base_success_rate, recipe_difficulty, ingredients, result_pill_name,
    effect_on_success, effect_on_failure, effect_on_explosion
) VALUES
(
    'Qi Gathering Pill', 'Mortal', 1, 0, 0.70, 30,
    '[{"item_name": "Spirit Herb", "quantity": 2, "grade_min": "Mortal"}]',
    'Qi Gathering Pill',
    '{"type": "qi_boost", "amount": 250}',
    '{"type": "poison", "heart_demon_delta": 0.01}',
    '{"type": "explosion", "qi_loss_pct": 0.15, "heart_demon_delta": 0.03}'
),
(
    'Foundation Pill', 'Earth', 3, 3, 0.60, 50,
    '[{"item_name": "Spirit Herb", "quantity": 3, "grade_min": "Mortal"}, {"item_name": "Monster Core", "quantity": 1, "grade_min": "Earth"}]',
    'Foundation Pill',
    '{"type": "qi_boost", "amount": 1000}',
    '{"type": "poison", "heart_demon_delta": 0.02}',
    '{"type": "explosion", "qi_loss_pct": 0.20, "heart_demon_delta": 0.04}'
),
(
    'Heart Cleansing Pill', 'Earth', 3, 5, 0.55, 60,
    '[{"item_name": "Spirit Herb", "quantity": 4, "grade_min": "Mortal"}, {"item_name": "Monster Core", "quantity": 2, "grade_min": "Earth"}]',
    'Heart Cleansing Pill',
    '{"type": "heart_demon_purge", "amount": 0.15}',
    '{"type": "poison", "heart_demon_delta": 0.02}',
    '{"type": "explosion", "qi_loss_pct": 0.25, "heart_demon_delta": 0.05}'
),
(
    'Nine Revolutions Spirit Pill', 'Heaven', 6, 10, 0.45, 80,
    '[{"item_name": "Monster Core", "quantity": 3, "grade_min": "Earth"}, {"item_name": "Heavenly Jade", "quantity": 1, "grade_min": "Heaven"}]',
    'Nine Revolutions Spirit Pill',
    '{"type": "qi_boost", "amount": 5000}',
    '{"type": "poison", "heart_demon_delta": 0.03}',
    '{"type": "explosion", "qi_loss_pct": 0.30, "heart_demon_delta": 0.08}'
);
