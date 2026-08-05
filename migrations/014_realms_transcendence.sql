-- ============================================================================
-- Heavenly Dao Engine — migration 014: 16 Realms × 9 Layers + Transcendence
-- ============================================================================

-- Existing rows were stored under the old 9-tier ladder with 4 sub-stages
-- (Early/Mid/Late/Peak). The new ladder has 16 realms × 9 layers, with
-- Void Refinement (炼虚) inserted between Soul Transformation (化神) and
-- Dao Fusion (合体), which shifts the old tiers 7-9 up by one.
--
--   old 6 (Spirit Severing 化神)  -> new 6  (Soul Transformation 化神)
--   old 7 (Dao Fusion 合体)       -> new 8  (Dao Fusion 合体)
--   old 8 (Tribulation 渡劫)      -> new 9  (Tribulation Transcendence 渡劫)
--   old 9 (Immortal 大乘)         -> new 10 (True Immortal 真仙)
--
-- Sub-stages expand into layers: 1->1, 2->3, 3->6, 4->9 (Peak = 9th Layer).
-- The remap is idempotent: re-running it maps already-mapped values to
-- themselves, so a re-run after a partial application is safe.
UPDATE cultivators SET
    realm_tier = CASE realm_tier
        WHEN 6 THEN 6         -- Soul Transformation 化神 (unchanged)
        WHEN 7 THEN 8         -- Dao Fusion 合体 (Void Refinement inserted above it)
        WHEN 8 THEN 9         -- Tribulation Transcendence 渡劫
        WHEN 9 THEN 10        -- True Immortal 真仙
        ELSE realm_tier END,
    realm_sub_stage = CASE realm_sub_stage
        WHEN 1 THEN 1
        WHEN 2 THEN 3
        WHEN 3 THEN 6
        WHEN 4 THEN 9
        ELSE realm_sub_stage END;

-- ---------------------------------------------------------------------------
-- Transcendence prestige columns
--   transcendence_count          — how many voluntary transcendences
--   legacy_passives              — JSON array of permanent passive keys granted
--   transcendence_capacity_bonus — flat Qi capacity that survives breakthroughs
--   transcendence_qi_gain_bonus  — flat Qi added to every /cultivate
-- ---------------------------------------------------------------------------
ALTER TABLE cultivators ADD COLUMN transcendence_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cultivators ADD COLUMN legacy_passives TEXT NOT NULL DEFAULT '[]';
ALTER TABLE cultivators ADD COLUMN transcendence_capacity_bonus INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cultivators ADD COLUMN transcendence_qi_gain_bonus INTEGER NOT NULL DEFAULT 0;
