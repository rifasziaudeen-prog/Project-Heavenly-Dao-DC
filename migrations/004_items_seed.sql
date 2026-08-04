-- ============================================================================
-- Heavenly Dao Engine — migration 004: Inventory & Items Seed
-- ============================================================================

-- Add equipment tracking columns to items if not present
ALTER TABLE items ADD COLUMN is_equipped INTEGER NOT NULL DEFAULT 0;
ALTER TABLE items ADD COLUMN equipped_slot TEXT;

-- ---------------------------------------------------------------------------
-- Item Templates catalog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    item_type   TEXT    NOT NULL,          -- Pill / Weapon / Technique_Scroll / Material / Talisman
    grade       TEXT    NOT NULL DEFAULT 'Mortal', -- Mortal / Earth / Heaven / Immortal / God
    description TEXT    NOT NULL DEFAULT '',
    effect_data TEXT    NOT NULL DEFAULT '{}',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Seed initial catalog items
INSERT OR IGNORE INTO item_templates (name, item_type, grade, description, effect_data) VALUES
-- Pills
('Qi Gathering Pill', 'Pill', 'Mortal', 'A basic pill condensed from spiritual herbs. Instantly restores 250 Qi.', '{"type": "qi_boost", "amount": 250}'),
('Foundation Pill', 'Pill', 'Earth', 'A mid-grade elixir forged with earth fire. Instantly restores 1,000 Qi.', '{"type": "qi_boost", "amount": 1000}'),
('Heart Cleansing Pill', 'Pill', 'Earth', 'Purges inner demons and soothes raging meridians. Clears 15% Heart Demon.', '{"type": "heart_demon_purge", "amount": 0.15}'),
('Nine Revolutions Spirit Pill', 'Pill', 'Heaven', 'A legendary elixir refined over nine cycles. Instantly restores 5,000 Qi.', '{"type": "qi_boost", "amount": 5000}'),
('Dao Heart Pill', 'Pill', 'Heaven', 'Anchors the soul against tribulation illusions. Clears 30% Heart Demon.', '{"type": "heart_demon_purge", "amount": 0.30}'),

-- Weapons
('Wooden Sword', 'Weapon', 'Mortal', 'A simple wooden sword used by novice disciples. Grants +5 Physique.', '{"type": "stat_buff", "stat": "physique", "amount": 5}'),
('Azure Dragon Sword', 'Weapon', 'Earth', 'Forged from cold meteor iron and dragon vein ore. Grants +15 Spirit.', '{"type": "stat_buff", "stat": "spirit", "amount": 15}'),
('Heavenly Flame Blade', 'Weapon', 'Heaven', 'Enveloped in divine karmic flames. Grants +35 Physique.', '{"type": "stat_buff", "stat": "physique", "amount": 35}'),

-- Technique Scrolls
('Basic Qi Breathing Manual', 'Technique_Scroll', 'Mortal', 'An entry-level mantra outlining Dantain flow. +5% breakthrough success rate.', '{"type": "breakthrough_aid", "bonus_percent": 5}'),
('Nine Heavens Tribulation Manual', 'Technique_Scroll', 'Earth', 'An ancient scroll analyzing lightning tribulation patterns. +12% breakthrough success rate.', '{"type": "breakthrough_aid", "bonus_percent": 12}'),
('Immortal Sovereign Scripture', 'Technique_Scroll', 'Heaven', 'Supreme scripture handed down from ancient immortals. +25% breakthrough success rate.', '{"type": "breakthrough_aid", "bonus_percent": 25}'),

-- Talismans
('Karmic Shield Talisman', 'Talisman', 'Earth', 'Consuming this talisman grants a Karmic Shield charm protecting against erasure.', '{"type": "protection", "charm_type": "karmic_shield"}'),
('Reincarnation Seed Talisman', 'Talisman', 'Heaven', 'Consuming this talisman grants a Reincarnation Seed charm.', '{"type": "protection", "charm_type": "reincarnation_seed"}'),
('Dao Heart Anchor Talisman', 'Talisman', 'Heaven', 'Consuming this talisman grants a Dao Heart Anchor charm.', '{"type": "protection", "charm_type": "dao_heart_anchor"}'),

-- Materials (for alchemy / crafting in Phase 3 step 2)
('Spirit Herb', 'Material', 'Mortal', 'A common medicinal herb containing trace spiritual Qi.', '{}'),
('Monster Core', 'Material', 'Earth', 'The crystallized energy core of a realm beast.', '{}'),
('Heavenly Jade', 'Material', 'Heaven', 'A rare gem resonant with universal Dao laws.', '{}');
