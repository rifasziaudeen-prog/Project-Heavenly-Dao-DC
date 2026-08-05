-- ============================================================================
-- Heavenly Dao Engine — migration 018: GLOBAL player profiles
--
-- Player data moves from per-guild isolation (UNIQUE(guild_id, user_id)) to a
-- single GLOBAL cultivation life per Discord user (UNIQUE(user_id)), identical
-- across every server the bot serves.
--
--   * `last_active_guild_id` tracks the server the player last played in, so
--     per-server leaderboards stay per-server (a player ranks on the board of
--     the server they last used).
--   * Duplicate accounts (the same user registered in several servers) are
--     merged keep-the-strongest — highest realm, then layer, then dantian Qi,
--     then oldest id — and every player-owned row (items, techniques, laws,
--     bonds, companions, reincarnation lives, realm runs, market listings,
--     combat history, soft references) is reparented onto the survivor.
--
-- Idempotent: re-running after a partial application is safe — the merge map
-- is rebuilt from scratch each run and is an identity map on already-merged
-- data. The runner tolerates the duplicate-column ALTER.
-- ============================================================================

-- 1) Track the last server the player was active in
ALTER TABLE cultivators ADD COLUMN last_active_guild_id INTEGER;
UPDATE cultivators SET last_active_guild_id = guild_id;

-- 2) Merge map: every cultivator row -> the surviving row for its user.
DROP TABLE IF EXISTS _hd_merge;
CREATE TEMP TABLE _hd_merge AS
SELECT c.id AS old_id, keep.id AS survivor_id
FROM cultivators c
JOIN (
    SELECT user_id, id FROM (
        SELECT user_id, id,
               ROW_NUMBER() OVER (
                   PARTITION BY user_id
                   ORDER BY realm_tier DESC, realm_sub_stage DESC,
                            qi_current DESC, id ASC
               ) AS rn
        FROM cultivators
    ) WHERE rn = 1
) keep ON keep.user_id = c.user_id;

-- 3) Reparent every player-owned row to the survivor
UPDATE items SET owner_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = items.owner_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = items.owner_id AND m.old_id != m.survivor_id);

UPDATE companions SET owner_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = companions.owner_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = companions.owner_id AND m.old_id != m.survivor_id);
UPDATE companions SET former_owner_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = companions.former_owner_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = companions.former_owner_id AND m.old_id != m.survivor_id);

UPDATE dao_protection_charms SET owner_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = dao_protection_charms.owner_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = dao_protection_charms.owner_id AND m.old_id != m.survivor_id);

UPDATE qi_buffer SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = qi_buffer.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = qi_buffer.cultivator_id AND m.old_id != m.survivor_id);

UPDATE breakthrough_log SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = breakthrough_log.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = breakthrough_log.cultivator_id AND m.old_id != m.survivor_id);

UPDATE cultivator_laws SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = cultivator_laws.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = cultivator_laws.cultivator_id AND m.old_id != m.survivor_id);

UPDATE cultivator_techniques SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = cultivator_techniques.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = cultivator_techniques.cultivator_id AND m.old_id != m.survivor_id);

UPDATE alchemy_attempts SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = alchemy_attempts.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = alchemy_attempts.cultivator_id AND m.old_id != m.survivor_id);

UPDATE reincarnation_log SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = reincarnation_log.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = reincarnation_log.cultivator_id AND m.old_id != m.survivor_id);

UPDATE secret_realm_runs SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = secret_realm_runs.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = secret_realm_runs.cultivator_id AND m.old_id != m.survivor_id);

UPDATE world_event_participants SET cultivator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = world_event_participants.cultivator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = world_event_participants.cultivator_id AND m.old_id != m.survivor_id);

-- world_events.created_by is PostgreSQL-only (SQLite has no such column)

UPDATE market_listings SET seller_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = market_listings.seller_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = market_listings.seller_id AND m.old_id != m.survivor_id);
UPDATE market_listings SET current_bidder_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = market_listings.current_bidder_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = market_listings.current_bidder_id AND m.old_id != m.survivor_id);

UPDATE trade_offers SET sender_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = trade_offers.sender_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = trade_offers.sender_id AND m.old_id != m.survivor_id);
UPDATE trade_offers SET recipient_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = trade_offers.recipient_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = trade_offers.recipient_id AND m.old_id != m.survivor_id);

UPDATE combat_log SET winner_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = combat_log.winner_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = combat_log.winner_id AND m.old_id != m.survivor_id);
UPDATE combat_log SET loser_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = combat_log.loser_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = combat_log.loser_id AND m.old_id != m.survivor_id);

-- Soft references (no FK) that point at a cultivator row
UPDATE cultivators SET master_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = cultivators.master_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = cultivators.master_id AND m.old_id != m.survivor_id);

UPDATE sects SET patriarch_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = sects.patriarch_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = sects.patriarch_id AND m.old_id != m.survivor_id);

-- 4) Bonds: reparent, collapse pairs that now collide, restore the pair index
DROP INDEX IF EXISTS idx_dao_bonds_pair;
UPDATE dao_bonds SET cultivator_a_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = dao_bonds.cultivator_a_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = dao_bonds.cultivator_a_id AND m.old_id != m.survivor_id);
UPDATE dao_bonds SET cultivator_b_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = dao_bonds.cultivator_b_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = dao_bonds.cultivator_b_id AND m.old_id != m.survivor_id);
UPDATE dao_bonds SET initiator_id = (SELECT m.survivor_id FROM _hd_merge m WHERE m.old_id = dao_bonds.initiator_id)
 WHERE EXISTS (SELECT 1 FROM _hd_merge m WHERE m.old_id = dao_bonds.initiator_id AND m.old_id != m.survivor_id);
DELETE FROM dao_bonds WHERE id NOT IN (
    SELECT MIN(id) FROM dao_bonds
    GROUP BY MIN(cultivator_a_id, cultivator_b_id),
             MAX(cultivator_a_id, cultivator_b_id)
);
-- A player cannot be their own partner — drop self-pairs left by the merge
DELETE FROM dao_bonds WHERE cultivator_a_id = cultivator_b_id;
CREATE UNIQUE INDEX IF NOT EXISTS idx_dao_bonds_pair
    ON dao_bonds(MIN(cultivator_a_id, cultivator_b_id),
                 MAX(cultivator_a_id, cultivator_b_id));

-- 5) Drop the duplicate cultivator rows and clean up the map
DELETE FROM cultivators WHERE id IN (
    SELECT old_id FROM _hd_merge WHERE old_id != survivor_id
);
DROP TABLE _hd_merge;

-- 6) Global uniqueness + per-server leaderboard indexes
DROP INDEX IF EXISTS idx_cultivators_guild_user;
CREATE UNIQUE INDEX IF NOT EXISTS idx_cultivators_user ON cultivators(user_id);
DROP INDEX IF EXISTS idx_cultivators_karma;
CREATE INDEX IF NOT EXISTS idx_cultivators_karma
    ON cultivators(last_active_guild_id, karma_points DESC);
DROP INDEX IF EXISTS idx_cultivators_realm;
CREATE INDEX IF NOT EXISTS idx_cultivators_realm
    ON cultivators(last_active_guild_id, realm_tier DESC, realm_sub_stage DESC, qi_current DESC);
