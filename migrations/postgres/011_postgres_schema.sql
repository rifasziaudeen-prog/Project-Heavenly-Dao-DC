-- ============================================================================
-- Heavenly Dao Engine — migration 011: PostgreSQL Enterprise Schema (v1.0.0)
-- Consolidated DDL for PostgreSQL 15+ with JSONB, GIN indexes, & Partitioning
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Cultivators
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cultivators (
    id                                SERIAL PRIMARY KEY,
    guild_id                          BIGINT NOT NULL,   -- home guild (legacy)
    user_id                           BIGINT NOT NULL,
    last_active_guild_id              BIGINT,            -- powers per-server leaderboards
    username                          TEXT   NOT NULL,
    gender                            TEXT   NOT NULL DEFAULT 'unknown' CHECK (gender IN ('male', 'female', 'non_binary', 'unknown')),
    realm_tier                        INTEGER NOT NULL DEFAULT 1 CHECK (realm_tier BETWEEN 1 AND 16),
    realm_sub_stage                   INTEGER NOT NULL DEFAULT 1 CHECK (realm_sub_stage BETWEEN 1 AND 9),
    qi_current                        INTEGER NOT NULL DEFAULT 0,
    qi_capacity                       INTEGER NOT NULL DEFAULT 100,
    physique                          TEXT    NOT NULL DEFAULT 'Mortal Meridian',
    titles                            JSONB   NOT NULL DEFAULT '[]'::jsonb,
    strength                          INTEGER NOT NULL DEFAULT 10,
    spirit                            INTEGER NOT NULL DEFAULT 10,
    physique_stat                     INTEGER NOT NULL DEFAULT 10,
    comprehension                     INTEGER NOT NULL DEFAULT 10,
    luck                              INTEGER NOT NULL DEFAULT 10,
    stat_points_unspent               INTEGER NOT NULL DEFAULT 0,
    sect_id                           INTEGER,
    spirit_stones                     INTEGER NOT NULL DEFAULT 0 CHECK (spirit_stones >= 0),
    alchemy_mastery                   REAL    NOT NULL DEFAULT 0.0 CHECK (alchemy_mastery BETWEEN 0.0 AND 100.0),
    alchemy_fame                      INTEGER NOT NULL DEFAULT 0,
    equipped_cauldron                 TEXT    NOT NULL DEFAULT 'Basic Bronze Cauldron',
    inherited_technique               TEXT,
    reincarnation_breakthrough_bonus  REAL    NOT NULL DEFAULT 0.0 CHECK (reincarnation_breakthrough_bonus BETWEEN 0.0 AND 0.25),
    rage_breakthrough_bonus_until     TIMESTAMPTZ,
    transcendence_count               INTEGER NOT NULL DEFAULT 0,
    legacy_passives                   JSONB   NOT NULL DEFAULT '[]'::jsonb,
    transcendence_capacity_bonus      INTEGER NOT NULL DEFAULT 0,
    transcendence_qi_gain_bonus       INTEGER NOT NULL DEFAULT 0,
    stored_qi_current                 INTEGER NOT NULL DEFAULT 0,
    stored_qi_max                     INTEGER NOT NULL DEFAULT 100 CHECK (stored_qi_max BETWEEN 100 AND 350),
    stored_qi_max_bonus               INTEGER NOT NULL DEFAULT 0,
    stored_qi_regen_bonus             INTEGER NOT NULL DEFAULT 0,
    last_breakthrough_at              TIMESTAMPTZ,
    created_at                        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cultivators_user UNIQUE (user_id)   -- GLOBAL players (018)
);
CREATE INDEX IF NOT EXISTS idx_cultivators_last_active
    ON cultivators(last_active_guild_id, realm_tier DESC);
CREATE INDEX IF NOT EXISTS idx_cultivators_spirit_stones ON cultivators USING btree (spirit_stones DESC);
CREATE INDEX IF NOT EXISTS idx_cultivators_titles_gin ON cultivators USING GIN (titles);

-- ---------------------------------------------------------------------------
-- Sects
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sects (
    id                 SERIAL PRIMARY KEY,
    guild_id           BIGINT NOT NULL,
    name               TEXT   NOT NULL,
    patriarch_id       INTEGER REFERENCES cultivators(id) ON DELETE SET NULL,
    array_level        INTEGER NOT NULL DEFAULT 1 CHECK (array_level BETWEEN 1 AND 5),
    treasury_stones    INTEGER NOT NULL DEFAULT 0 CHECK (treasury_stones >= 0),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sects_guild_name UNIQUE (guild_id, name)
);

-- ---------------------------------------------------------------------------
-- Dao Bonds
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dao_bonds (
    id                 SERIAL PRIMARY KEY,
    guild_id           BIGINT NOT NULL,
    cultivator_a_id    INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    cultivator_b_id    INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    bond_type          TEXT    NOT NULL CHECK (bond_type IN ('dao_companion', 'sworn_sibling', 'master_disciple')),
    bond_tier          INTEGER NOT NULL DEFAULT 1 CHECK (bond_tier BETWEEN 1 AND 5),
    affinity_xp        INTEGER NOT NULL DEFAULT 0,
    bonded_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Items
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id                 SERIAL PRIMARY KEY,
    owner_id           INTEGER REFERENCES cultivators(id) ON DELETE CASCADE,
    item_name          TEXT    NOT NULL,
    item_type          TEXT    NOT NULL CHECK (item_type IN ('Pill', 'Weapon', 'Scroll', 'Talisman', 'Material')),
    grade              TEXT    NOT NULL DEFAULT 'Mortal' CHECK (grade IN ('Mortal', 'Earth', 'Heaven', 'Immortal', 'God')),
    quantity           INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    effect_data        JSONB   NOT NULL DEFAULT '{}'::jsonb,
    is_equipped        BOOLEAN NOT NULL DEFAULT FALSE,
    equipped_slot      TEXT    CHECK (equipped_slot IN ('weapon', 'technique')),
    acquired_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_items_owner ON items(owner_id);
CREATE INDEX IF NOT EXISTS idx_items_effect_gin ON items USING GIN (effect_data);

-- ---------------------------------------------------------------------------
-- Item Templates Catalog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item_templates (
    id                 SERIAL PRIMARY KEY,
    item_name          TEXT    NOT NULL UNIQUE,
    item_type          TEXT    NOT NULL,
    grade              TEXT    NOT NULL DEFAULT 'Mortal',
    base_effect_data   JSONB   NOT NULL DEFAULT '{}'::jsonb,
    description        TEXT    NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Qi Buffer (Partitioned by Range)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qi_buffer (
    id                 SERIAL,
    cultivator_id      INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    qi_amount          INTEGER NOT NULL CHECK (qi_amount > 0),
    source             TEXT    NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE qi_buffer_default PARTITION OF qi_buffer DEFAULT;

-- ---------------------------------------------------------------------------
-- Alchemy Recipes & Attempts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alchemy_recipes (
    id                 SERIAL PRIMARY KEY,
    recipe_name        TEXT    NOT NULL UNIQUE,
    pill_grade         TEXT    NOT NULL DEFAULT 'Mortal',
    min_mastery        REAL    NOT NULL DEFAULT 0.0,
    required_ingredients JSONB NOT NULL DEFAULT '[]'::jsonb,
    cauldron_required  TEXT    NOT NULL DEFAULT 'Basic Bronze Cauldron',
    base_success_rate  REAL    NOT NULL DEFAULT 0.50,
    pill_effect_json   JSONB   NOT NULL DEFAULT '{}'::jsonb,
    description        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS alchemy_attempts (
    id                 SERIAL PRIMARY KEY,
    cultivator_id      INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    recipe_id          INTEGER NOT NULL REFERENCES alchemy_recipes(id) ON DELETE CASCADE,
    stage_1_score      INTEGER NOT NULL,
    stage_2_score      INTEGER NOT NULL,
    stage_3_score      INTEGER NOT NULL,
    final_score        INTEGER NOT NULL,
    result             TEXT    NOT NULL CHECK (result IN ('SUCCESS', 'MIRACLE', 'FAILURE', 'EXPLOSION')),
    attempted_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Secret Realms & Runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS secret_realm_templates (
    id                 SERIAL PRIMARY KEY,
    name               TEXT    NOT NULL UNIQUE,
    min_realm_tier     INTEGER NOT NULL DEFAULT 1,
    node_count         INTEGER NOT NULL DEFAULT 3,
    qi_cost            INTEGER NOT NULL DEFAULT 50,
    description        TEXT    NOT NULL,
    drop_table_json    JSONB   NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS secret_realm_runs (
    id                 SERIAL PRIMARY KEY,
    cultivator_id      INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    realm_name         TEXT    NOT NULL,
    current_node       INTEGER NOT NULL DEFAULT 1,
    max_nodes          INTEGER NOT NULL DEFAULT 3,
    status             TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'retreated', 'failed')),
    accumulated_loot   JSONB   NOT NULL DEFAULT '[]'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Reincarnation Log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reincarnation_log (
    id                     SERIAL PRIMARY KEY,
    cultivator_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    cycle_from             INTEGER NOT NULL,
    cycle_to               INTEGER NOT NULL,
    reason                 TEXT    NOT NULL,
    realm_tier_at_death    INTEGER NOT NULL,
    comprehension_retained INTEGER NOT NULL,
    luck_retained          INTEGER NOT NULL,
    technique_retained     TEXT,
    epitaph                TEXT    NOT NULL,
    reincarnated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- World Events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS world_events (
    id                     SERIAL PRIMARY KEY,
    guild_id               BIGINT NOT NULL,
    event_type             TEXT   NOT NULL CHECK (event_type IN ('demon_beast_siege', 'heavenly_tribulation_rain', 'ancient_ruin_awakening', 'sect_war', 'dao_competition')),
    scheduled_at           TIMESTAMPTZ NOT NULL,
    started_at             TIMESTAMPTZ,
    ended_at               TIMESTAMPTZ,
    status                 TEXT   NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'completed', 'failed', 'cancelled')),
    difficulty_rating      INTEGER NOT NULL DEFAULT 1,
    boss_hp_max            INTEGER NOT NULL,
    boss_hp_current        INTEGER NOT NULL,
    current_phase          INTEGER NOT NULL DEFAULT 1,
    narrative_state        TEXT   NOT NULL DEFAULT 'A cosmic aura descends...',
    participation_rewards  JSONB  NOT NULL DEFAULT '{}'::jsonb,
    created_by             INTEGER REFERENCES cultivators(id) ON DELETE SET NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS world_event_participants (
    event_id               INTEGER NOT NULL REFERENCES world_events(id) ON DELETE CASCADE,
    cultivator_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    sect_id                INTEGER REFERENCES sects(id) ON DELETE SET NULL,
    damage_dealt           INTEGER NOT NULL DEFAULT 0,
    qi_contributed         INTEGER NOT NULL DEFAULT 0,
    healing_done           INTEGER NOT NULL DEFAULT 0,
    final_rank             INTEGER,
    reward_claimed         BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, cultivator_id)
);

-- ---------------------------------------------------------------------------
-- Dao Laws
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dao_laws (
    id                     SERIAL PRIMARY KEY,
    name                   TEXT   NOT NULL UNIQUE,
    name_zh                TEXT   NOT NULL,
    law_tier               INTEGER DEFAULT 1 CHECK (law_tier BETWEEN 1 AND 5),
    comprehension_required INTEGER NOT NULL DEFAULT 200,
    realm_required         INTEGER NOT NULL DEFAULT 5,
    mastery_effect         JSONB  NOT NULL DEFAULT '{}'::jsonb,
    law_lore               TEXT   NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cultivator_laws (
    cultivator_id          INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    law_id                 INTEGER NOT NULL REFERENCES dao_laws(id) ON DELETE CASCADE,
    mastery_percentage     REAL   NOT NULL DEFAULT 0.0 CHECK (mastery_percentage BETWEEN 0.0 AND 100.0),
    insights_gained        INTEGER NOT NULL DEFAULT 0,
    milestone_25_reached   BOOLEAN NOT NULL DEFAULT FALSE,
    milestone_50_reached   BOOLEAN NOT NULL DEFAULT FALSE,
    milestone_75_reached   BOOLEAN NOT NULL DEFAULT FALSE,
    milestone_100_reached  BOOLEAN NOT NULL DEFAULT FALSE,
    last_enlightenment_at  TIMESTAMPTZ,
    PRIMARY KEY (cultivator_id, law_id)
);

-- ---------------------------------------------------------------------------
-- Auction House & Trade Offers
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_listings (
    id                     SERIAL PRIMARY KEY,
    seller_id              INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    item_id                INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity               INTEGER NOT NULL DEFAULT 1,
    price                  INTEGER NOT NULL,
    buyout_price           INTEGER,
    current_bid            INTEGER NOT NULL DEFAULT 0,
    current_bidder_id      INTEGER REFERENCES cultivators(id) ON DELETE SET NULL,
    status                 TEXT   NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'sold', 'expired', 'cancelled')),
    listed_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at             TIMESTAMPTZ NOT NULL,
    sold_at                TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS trade_offers (
    id                     SERIAL PRIMARY KEY,
    sender_id              INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    recipient_id           INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    item_id                INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity               INTEGER NOT NULL DEFAULT 1,
    status                 TEXT   NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at             TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '10 minutes')
);

-- ---------------------------------------------------------------------------
-- Guild Config & Audit Log (Partitioned)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id               BIGINT PRIMARY KEY,
    xianxia_terms_language TEXT   NOT NULL DEFAULT 'bilingual' CHECK (xianxia_terms_language IN ('english', 'bilingual')),
    admin_role_id          BIGINT,
    erasure_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    announcement_channel_id BIGINT,
    dao_role_to_gender     JSONB  NOT NULL DEFAULT '{}'::jsonb,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id                     SERIAL,
    guild_id               BIGINT NOT NULL,
    user_id                BIGINT,
    action                 TEXT   NOT NULL,
    details                JSONB  NOT NULL DEFAULT '{}'::jsonb,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_log_default PARTITION OF audit_log DEFAULT;

-- ---------------------------------------------------------------------------
-- Combat (Contendance): techniques, registers, and battle log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS techniques (
    id             SERIAL PRIMARY KEY,
    name           TEXT   NOT NULL UNIQUE,
    name_zh        TEXT   NOT NULL,
    quality        TEXT   NOT NULL DEFAULT 'White' CHECK (quality IN ('White','Green','Blue','Purple','Orange','Red')),
    law_affinity   TEXT,
    base_damage    INTEGER NOT NULL DEFAULT 8,
    stored_qi_cost INTEGER NOT NULL DEFAULT 10,
    description    TEXT   NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cultivator_techniques (
    cultivator_id   INTEGER NOT NULL REFERENCES cultivators(id) ON DELETE CASCADE,
    technique_id    INTEGER NOT NULL REFERENCES techniques(id) ON DELETE CASCADE,
    mastery_progress REAL  NOT NULL DEFAULT 0.0 CHECK (mastery_progress BETWEEN 0.0 AND 100.0),
    entries         JSONB   NOT NULL DEFAULT '[]'::jsonb,
    times_used      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cultivator_id, technique_id)
);
CREATE INDEX IF NOT EXISTS idx_cult_tech_pg ON cultivator_techniques(cultivator_id, mastery_progress DESC);

CREATE TABLE IF NOT EXISTS combat_log (
    id             SERIAL PRIMARY KEY,
    guild_id       BIGINT NOT NULL,
    winner_id      INTEGER REFERENCES cultivators(id) ON DELETE SET NULL,
    loser_id       INTEGER REFERENCES cultivators(id) ON DELETE SET NULL,
    mode           TEXT   NOT NULL CHECK (mode IN ('duel', 'battle')),
    rounds         INTEGER NOT NULL DEFAULT 1,
    reason         TEXT   NOT NULL DEFAULT 'defeat',
    wager_type     TEXT   NOT NULL DEFAULT 'none',
    wager_amount   INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_combat_log_pg ON combat_log(guild_id, created_at);
