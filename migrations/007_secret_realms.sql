-- ============================================================================
-- Heavenly Dao Engine — migration 007: Secret Realms System
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Secret Realm Templates Catalog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS secret_realm_templates (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT    NOT NULL UNIQUE,
    min_realm_tier     INTEGER NOT NULL DEFAULT 1,
    node_count         INTEGER NOT NULL DEFAULT 3,
    qi_cost            INTEGER NOT NULL DEFAULT 50,
    description        TEXT    NOT NULL,
    drop_table_json    TEXT    NOT NULL DEFAULT '[]',
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Active Secret Realm Exploration Runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS secret_realm_runs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivator_id      INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    realm_name         TEXT    NOT NULL,
    current_node       INTEGER NOT NULL DEFAULT 1,
    max_nodes          INTEGER NOT NULL DEFAULT 3,
    status             TEXT    NOT NULL DEFAULT 'active', -- 'active', 'completed', 'retreated', 'failed'
    accumulated_loot   TEXT    NOT NULL DEFAULT '[]',     -- JSON array of items won
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_secret_realm_runs_cultivator
    ON secret_realm_runs(cultivator_id, status);

-- Seed initial Secret Realms catalog
INSERT OR IGNORE INTO secret_realm_templates (
    name, min_realm_tier, node_count, qi_cost, description, drop_table_json
) VALUES
(
    'Ancient Sword Tomb', 1, 3, 50,
    'A misty valley filled with shattered sword monuments and lingering intent.',
    '[{"name": "Spirit Herb", "type": "Material", "grade": "Mortal", "weight": 50}, {"name": "Iron Sword", "type": "Weapon", "grade": "Mortal", "weight": 30}, {"name": "Qi Gathering Pill", "type": "Pill", "grade": "Mortal", "weight": 20}]'
),
(
    'Emerald Herb Valley', 3, 4, 200,
    'An ancient celestial garden overgrown with rare herbs and guarded by spirit beasts.',
    '[{"name": "Spirit Herb", "type": "Material", "grade": "Mortal", "weight": 40}, {"name": "Monster Core", "type": "Material", "grade": "Earth", "weight": 35}, {"name": "Foundation Pill", "type": "Pill", "grade": "Earth", "weight": 25}]'
),
(
    'Dragon Blood Cavern', 4, 5, 500,
    'Deep subterranean caverns flowing with primordial dragon essence and ancient traps.',
    '[{"name": "Monster Core", "type": "Material", "grade": "Earth", "weight": 40}, {"name": "Heavenly Jade", "type": "Material", "grade": "Heaven", "weight": 25}, {"name": "Sword Intent Scroll", "type": "Technique_Scroll", "grade": "Earth", "weight": 20}, {"name": "Nine Revolutions Spirit Pill", "type": "Pill", "grade": "Heaven", "weight": 15}]'
);
