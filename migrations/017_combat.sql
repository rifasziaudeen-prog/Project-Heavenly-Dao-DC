-- ============================================================================
-- Heavenly Dao Engine — migration 017: Contendance combat (techniques & log)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Technique catalog (quality tiers White -> Red; law_affinity ties techniques
-- to Dao Laws — see migration 016 for the law ladder)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS techniques (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL UNIQUE,
    name_zh        TEXT    NOT NULL,
    quality        TEXT    NOT NULL DEFAULT 'White'  -- White/Green/Blue/Purple/Orange/Red
                     CHECK (quality IN ('White','Green','Blue','Purple','Orange','Red')),
    law_affinity   TEXT,                              -- NULL = universal
    base_damage    INTEGER NOT NULL DEFAULT 8,
    stored_qi_cost INTEGER NOT NULL DEFAULT 10,
    description    TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO techniques
    (name, name_zh, quality, law_affinity, base_damage, stored_qi_cost, description)
VALUES
    ('Qi Burst', '灵气爆发', 'White', NULL, 8, 10, 'A raw pulse of spiritual energy. The first technique every cultivator learns.'),
    ('Body Tempering Strike', '锻体拳', 'White', NULL, 9, 10, 'A disciplined fist backed by tempered flesh.'),
    ('Falling Leaf Step', '落叶身法', 'Green', NULL, 14, 15, 'A drifting step that slips between openings.'),
    ('Void Step', '虚空步', 'Green', 'Law of Space', 15, 16, 'Fold the gap between you and your foe.'),
    ('Temporal Slash', '时光斩', 'Blue', 'Law of Time', 22, 22, 'A strike that arrives a breath before it is thrown.'),
    ('Sword Intent Slash', '剑意斩', 'Blue', 'Law of Sword', 24, 24, 'Will made edge.'),
    ('Karmic Threads', '因果丝', 'Purple', 'Law of Karma', 32, 30, 'Tie your enemy to debts they cannot pay.'),
    ('Alchemical Flame Burst', '丹火爆', 'Purple', 'Law of Alchemy', 33, 32, 'A cauldron-stoked detonation.'),
    ('Nine Heavens Thunder', '九霄雷霆', 'Orange', NULL, 45, 40, 'Call down the tribulation''s own lightning.'),
    ('Void Fold', '虚空折叠', 'Orange', 'Law of Space', 47, 42, 'Wrap space around the blow and let go.'),
    ('Sword of Annihilation', '灭世剑', 'Red', 'Law of Sword', 62, 55, 'The sword that ends worlds.'),
    ('Dao Ancestor Palm', '道祖掌', 'Red', NULL, 60, 52, 'A palm that carries the weight of the Dao itself.');

-- ---------------------------------------------------------------------------
-- Cultivator technique register (mastery + rolled entries)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cultivator_techniques (
    cultivator_id   INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    technique_id    INTEGER NOT NULL REFERENCES techniques(id) ON DELETE CASCADE,
    mastery_progress REAL   NOT NULL DEFAULT 0.0 CHECK (mastery_progress BETWEEN 0.0 AND 100.0),
    entries         TEXT    NOT NULL DEFAULT '[]',   -- JSON array of entry keys
    times_used      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (cultivator_id, technique_id)
);
CREATE INDEX IF NOT EXISTS idx_cult_tech_cultivator
    ON cultivator_techniques(cultivator_id, mastery_progress DESC);

-- ---------------------------------------------------------------------------
-- Combat log (duels & beast battles) for leaderboards / history
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS combat_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id       INTEGER NOT NULL,
    winner_id      INTEGER,                          -- cultivators.id (NULL on retreat-no-winner)
    loser_id       INTEGER,
    mode           TEXT    NOT NULL,                 -- duel / battle
    rounds         INTEGER NOT NULL DEFAULT 1,
    reason         TEXT    NOT NULL DEFAULT 'defeat',-- defeat / retreat / dao_heart / burn
    wager_type     TEXT,                             -- stones / none
    wager_amount   INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_combat_log_guild ON combat_log(guild_id, created_at);

-- ---------------------------------------------------------------------------
-- Comprehension Sand — consumed (with spirit stones) to reroll technique entries
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO item_templates (name, item_type, grade, description, effect_data) VALUES
('Comprehension Sand', 'Material', 'Heaven', 'Grain of crystallized insight. Used to reroll technique entries.', '{}');
