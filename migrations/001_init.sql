-- ============================================================================
-- Heavenly Dao Engine — migration 001: initial schema (SQLite / Phase 1)
--
-- Adapted from the v2.0 blueprint with ALL Kimi review P0 fixes applied:
--   * cultivators: surrogate INTEGER PK + UNIQUE(guild_id, user_id)
--     (fixes the multi-guild player collision bug)
--   * append-only qi_buffer + qi_hourly_stats (memory-buffered batch writes)
--   * JSON payloads stored as TEXT (SQLite) — validation stays in Python
--   * per-guild isolation on every table that carries game state
--
-- Portability notes: see MIGRATION.md for the PostgreSQL mapping.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Sects (defined first because cultivators FK into it)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sects (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL UNIQUE,
    patriarch_id   INTEGER,                 -- cultivators.id (soft ref; circular FK avoided)
    alignment      TEXT    NOT NULL DEFAULT 'Neutral',  -- Righteous / Demonic / Neutral
    core_qi_pool   INTEGER NOT NULL DEFAULT 0,
    array_level    INTEGER NOT NULL DEFAULT 1,
    treasury_stones INTEGER NOT NULL DEFAULT 0,
    max_members    INTEGER NOT NULL DEFAULT 20,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Cultivators — the heart of the system
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cultivators (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                INTEGER NOT NULL,                 -- Discord snowflake
    guild_id               INTEGER NOT NULL,                 -- per-guild isolation
    username               TEXT    NOT NULL DEFAULT 'Unknown',
    title                  TEXT,
    titles                 TEXT    NOT NULL DEFAULT '[]',    -- JSON array of titles
    realm_tier             INTEGER NOT NULL DEFAULT 1,       -- 1..9
    realm_sub_stage        INTEGER NOT NULL DEFAULT 1,       -- 1..4 (Early/Mid/Late/Peak)
    qi_current             INTEGER NOT NULL DEFAULT 0,
    qi_capacity            INTEGER NOT NULL DEFAULT 1000,
    cultivation_physique   TEXT    NOT NULL DEFAULT 'Mortal Meridian',
    strength               INTEGER NOT NULL DEFAULT 10,
    spirit                 INTEGER NOT NULL DEFAULT 10,
    physique               INTEGER NOT NULL DEFAULT 10,
    comprehension          INTEGER NOT NULL DEFAULT 10,
    luck                   INTEGER NOT NULL DEFAULT 5,
    stat_points            INTEGER NOT NULL DEFAULT 0,       -- earned via breakthroughs
    karma_points           INTEGER NOT NULL DEFAULT 0,       -- + righteous / - demonic
    heart_demon_ratio      REAL    NOT NULL DEFAULT 0.0,     -- 0.0..1.0
    sect_id                INTEGER REFERENCES sects(id) ON DELETE SET NULL,
    sect_rank              TEXT    NOT NULL DEFAULT 'Outer Disciple',
    master_id              INTEGER,
    failure_streak         INTEGER NOT NULL DEFAULT 0,       -- breakthrough pity (Dao Mercy)
    reincarnation_cycle    INTEGER NOT NULL DEFAULT 0,
    message_qi_count       INTEGER NOT NULL DEFAULT 0,       -- rolling hourly cap
    message_qi_window_start TEXT,                            -- epoch seconds (str)
    last_cultivate_at      TEXT,
    created_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- P0 fix: one player per guild
CREATE UNIQUE INDEX IF NOT EXISTS idx_cultivators_guild_user
    ON cultivators(guild_id, user_id);

-- Missing-index fixes from the review
CREATE INDEX IF NOT EXISTS idx_cultivators_sect
    ON cultivators(sect_id) WHERE sect_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cultivators_karma
    ON cultivators(guild_id, karma_points DESC);
CREATE INDEX IF NOT EXISTS idx_cultivators_realm
    ON cultivators(guild_id, realm_tier DESC, realm_sub_stage DESC, qi_current DESC);

-- ---------------------------------------------------------------------------
-- Dao Companions / Harem
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id              INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    name                  TEXT    NOT NULL,
    title                 TEXT,
    physique              TEXT    NOT NULL DEFAULT 'Pure Yin Body',
    rarity                TEXT    NOT NULL DEFAULT 'Common',  -- Common/Rare/Immortal/Divine
    favorability          INTEGER NOT NULL DEFAULT 0,         -- 0..1000
    intimacy_level        INTEGER NOT NULL DEFAULT 1,
    dual_cultivation_bonus REAL   NOT NULL DEFAULT 1.05,
    personality_vector    TEXT    NOT NULL DEFAULT '[0,0,0,0,0]', -- [Pride,Loyalty,Ambition,Jealousy,Wisdom]
    mood_current          TEXT    NOT NULL DEFAULT 'neutral',
    mood_decay_rate       REAL    NOT NULL DEFAULT 0.05,
    last_interaction_at   TEXT,
    secret_desire         TEXT,
    traumatic_memory      TEXT,
    cultivation_path      TEXT,                                -- Yin/Yang/Sword/Pill
    synergy_bonus         TEXT    NOT NULL DEFAULT '{}',
    lore_backstory        TEXT,                                -- cached LLM backstory (once)
    status                TEXT    NOT NULL DEFAULT 'active',
    former_owner_id       INTEGER,
    lore_epitaph          TEXT,
    unlocked_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_companions_owner
    ON companions(owner_id, intimacy_level DESC);

-- ---------------------------------------------------------------------------
-- Inventory / artifacts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    item_type   TEXT    NOT NULL,          -- Pill/Weapon/Technique_Scroll/Material/Talisman
    grade       TEXT    NOT NULL DEFAULT 'Mortal',  -- Mortal/Earth/Heaven/Immortal/God
    effect_data TEXT    NOT NULL DEFAULT '{}',
    quantity    INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_items_owner_type
    ON items(owner_id, item_type, grade);

-- ---------------------------------------------------------------------------
-- Secret Realms (instances)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS secret_realms (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    min_realm_tier   INTEGER NOT NULL DEFAULT 1,
    max_participants INTEGER NOT NULL DEFAULT 5,
    is_active        INTEGER NOT NULL DEFAULT 1,
    realm_data       TEXT    NOT NULL DEFAULT '{}',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Qi pipeline: append-only buffer + hourly aggregate (review P0 fix)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qi_buffer (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivator_id INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    guild_id      INTEGER NOT NULL,
    qi_amount     INTEGER NOT NULL,
    source        TEXT    NOT NULL,        -- message/cultivate/sect_array/dual_cultivation
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_qi_buffer_cultivator
    ON qi_buffer(cultivator_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qi_buffer_guild_time
    ON qi_buffer(guild_id, created_at);

-- Throughput stats for the Heaven Panel
CREATE TABLE IF NOT EXISTS qi_hourly_stats (
    guild_id      INTEGER NOT NULL,
    hour_bucket   TEXT    NOT NULL,        -- 'YYYY-MM-DD HH:00:00' (UTC)
    message_count INTEGER NOT NULL DEFAULT 0,
    qi_total      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, hour_bucket)
);

-- ---------------------------------------------------------------------------
-- Heavenly Dao Erasure counterplay (dao_protection_charms)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dao_protection_charms (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id         INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    charm_type       TEXT    NOT NULL
                     CHECK (charm_type IN ('karmic_shield','reincarnation_seed','dao_heart_anchor')),
    protection_level INTEGER NOT NULL DEFAULT 1,
    consumed_at      TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_charms_owner
    ON dao_protection_charms(owner_id) WHERE consumed_at IS NULL;

-- ---------------------------------------------------------------------------
-- Audit / telemetry
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS breakthrough_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivator_id    INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    realm_tier       INTEGER NOT NULL,
    success          INTEGER NOT NULL,
    probability      REAL    NOT NULL,
    heart_demon_ratio REAL   NOT NULL DEFAULT 0,
    was_erased       INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS anti_cheat_flags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    flag_type  TEXT    NOT NULL,           -- qi_rate_abuse/repeat_spam/...
    severity   INTEGER NOT NULL DEFAULT 1,
    reason     TEXT,
    resolved   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_flags_guild ON anti_cheat_flags(guild_id, resolved);

CREATE TABLE IF NOT EXISTS llm_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    guild_id      INTEGER NOT NULL,
    model         TEXT    NOT NULL,
    prompt_purpose TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_llm_usage_user_time ON llm_usage(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_llm_usage_global_time ON llm_usage(created_at);

-- ---------------------------------------------------------------------------
-- World events / calamities (scheduler exists in Phase 1; mechanics Phase 4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_events (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id             INTEGER NOT NULL,
    event_type           TEXT    NOT NULL, -- demon_beast_siege/heavenly_tribulation_rain/ancient_ruin_awakening/sect_war
    scheduled_at         TEXT    NOT NULL,
    status               TEXT    NOT NULL DEFAULT 'pending', -- pending/active/completed/failed
    difficulty_rating    INTEGER NOT NULL DEFAULT 1,
    participation_rewards TEXT   NOT NULL DEFAULT '{}',
    boss_hp_current      INTEGER,
    boss_hp_max          INTEGER,
    narrative_state      TEXT,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_world_events_sched
    ON world_events(guild_id, status, scheduled_at);

CREATE TABLE IF NOT EXISTS world_event_participants (
    event_id        INTEGER NOT NULL REFERENCES world_events(id) ON DELETE CASCADE,
    cultivator_id   INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    damage_dealt    INTEGER NOT NULL DEFAULT 0,
    qi_contributed  INTEGER NOT NULL DEFAULT 0,
    final_rank      INTEGER,
    reward_claimed  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (event_id, cultivator_id)
);

-- ---------------------------------------------------------------------------
-- Narrative template engine (Tier 2 — zero LLM cost)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS narrative_templates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    category   TEXT    NOT NULL,
    fragment   TEXT    NOT NULL,
    weight     REAL    NOT NULL DEFAULT 1.0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_templates_category ON narrative_templates(category);

-- ---------------------------------------------------------------------------
-- Per-guild configuration
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id               INTEGER PRIMARY KEY,
    qi_enabled_channels    TEXT NOT NULL DEFAULT '[]',  -- whitelist; [] = all channels
    qi_disabled_channels   TEXT NOT NULL DEFAULT '[]',  -- blacklist (spam channels)
    admin_role_id          INTEGER,
    admin_user_id          INTEGER,
    xianxia_terms_language TEXT NOT NULL DEFAULT 'bilingual',
    erasure_enabled        INTEGER NOT NULL DEFAULT 1,
    groq_enabled           INTEGER NOT NULL DEFAULT 0,
    system_channel_id      INTEGER,
    broadcast_channel_id   INTEGER,
    updated_at             TEXT
);
