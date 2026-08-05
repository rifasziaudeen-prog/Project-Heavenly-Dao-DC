-- ============================================================================
-- Heavenly Dao Engine — migration 016: Dao Law Ranks (5-rank system)
-- ============================================================================
--
-- The old milestone system used 25/50/75/100 keys in each law's
-- mastery_effect JSON. The v1.6.0 rank system unlocks at 20/40/60/80/100
-- (Rank 1-5). Each law's effect ladder is re-keyed accordingly, with new
-- Rank-5 capstones. The legacy milestone_*_reached columns on
-- cultivator_laws are backfilled for data hygiene but are no longer used —
-- ranks are derived from mastery_percentage (core/dao_laws.py).

UPDATE dao_laws SET mastery_effect =
    '{"20": {"dodge_bonus": 0.10}, "40": {"technique": "Void Step"}, "60": {"movement_bonus": 0.25}, "80": {"teleport": true}, "100": {"space_dominion": true}}'
    WHERE name = 'Law of Space';

UPDATE dao_laws SET mastery_effect =
    '{"20": {"cooldown_reduction": 0.10}, "40": {"technique": "Temporal Cultivation"}, "60": {"qi_accumulation_bonus": 0.15}, "80": {"rewind_breakthrough": true}, "100": {"time_seal": true}}'
    WHERE name = 'Law of Time';

UPDATE dao_laws SET mastery_effect =
    '{"20": {"karma_gain_bonus": 0.10}, "40": {"see_auras": true}, "60": {"breakthrough_bonus": 0.20}, "80": {"revive_once": true}, "100": {"karmic_justice": true}}'
    WHERE name = 'Law of Karma';

UPDATE dao_laws SET mastery_effect =
    '{"20": {"damage_bonus": 0.15}, "40": {"passive": "Sword Intent"}, "60": {"crit_rate_bonus": 0.30}, "80": {"execute_sub_20": true}, "100": {"sword_dominion": true}}'
    WHERE name = 'Law of Sword';

UPDATE dao_laws SET mastery_effect =
    '{"20": {"pill_success_bonus": 0.10}, "40": {"cauldron_grade": "Heavenly Flame"}, "60": {"pill_potency_bonus": 0.25}, "80": {"refine_god_grade": true}, "100": {"alchemical_transcendence": true}}'
    WHERE name = 'Law of Alchemy';

-- Legacy milestone booleans backfill (kept for schema stability; ranks now
-- derive from mastery_percentage).
UPDATE cultivator_laws SET
    milestone_25_reached = CASE WHEN mastery_percentage >= 25 THEN 1 ELSE 0 END,
    milestone_50_reached = CASE WHEN mastery_percentage >= 50 THEN 1 ELSE 0 END,
    milestone_75_reached = CASE WHEN mastery_percentage >= 75 THEN 1 ELSE 0 END,
    milestone_100_reached = CASE WHEN mastery_percentage >= 100 THEN 1 ELSE 0 END;
