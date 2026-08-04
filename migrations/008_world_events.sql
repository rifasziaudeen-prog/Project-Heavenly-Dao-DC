-- ============================================================================
-- Heavenly Dao Engine — migration 008: World Events & Heavenly Calamities
-- ============================================================================

-- ---------------------------------------------------------------------------
-- World Events Catalog & Active Runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_events (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id               INTEGER NOT NULL,
    event_type             TEXT    NOT NULL CHECK (event_type IN ('demon_beast_siege', 'heavenly_tribulation_rain', 'ancient_ruin_awakening', 'sect_war', 'dao_competition')),
    scheduled_at           TEXT    NOT NULL,
    started_at             TEXT,
    ended_at               TEXT,
    status                 TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'completed', 'failed', 'cancelled')),
    difficulty_rating      INTEGER NOT NULL DEFAULT 1,
    boss_hp_max            INTEGER NOT NULL,
    boss_hp_current        INTEGER NOT NULL,
    current_phase          INTEGER NOT NULL DEFAULT 1,
    narrative_state        TEXT    NOT NULL DEFAULT 'A cosmic aura descends...',
    participation_rewards  TEXT    NOT NULL DEFAULT '{}',
    created_by             INTEGER REFERENCES cultivators(id) ON DELETE SET NULL,
    created_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_world_events_guild_status
    ON world_events(guild_id, status);

-- ---------------------------------------------------------------------------
-- World Event Participants
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_event_participants (
    event_id               INTEGER NOT NULL REFERENCES world_events(id) ON DELETE CASCADE,
    cultivator_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    sect_id                INTEGER REFERENCES sects(id) ON DELETE SET NULL,
    damage_dealt           INTEGER NOT NULL DEFAULT 0,
    qi_contributed         INTEGER NOT NULL DEFAULT 0,
    healing_done           INTEGER NOT NULL DEFAULT 0,
    final_rank             INTEGER,
    reward_claimed         BOOLEAN NOT NULL DEFAULT 0,
    joined_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (event_id, cultivator_id)
);
CREATE INDEX IF NOT EXISTS idx_world_event_participants_rank
    ON world_event_participants(event_id, damage_dealt DESC);

-- ---------------------------------------------------------------------------
-- World Event Phases
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_event_phases (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id               INTEGER NOT NULL REFERENCES world_events(id) ON DELETE CASCADE,
    phase_number           INTEGER NOT NULL,
    phase_name             TEXT    NOT NULL,
    hp_threshold_percent   INTEGER NOT NULL,
    boss_damage_multiplier REAL    NOT NULL DEFAULT 1.0,
    spawn_adds             BOOLEAN NOT NULL DEFAULT 0,
    special_mechanic       TEXT,
    narrative_template     TEXT    NOT NULL
);
