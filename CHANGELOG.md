# Changelog

All notable changes to the **Heavenly Dao Engine** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.0] — 2026-08-05 — Dao Law Ranks + Aptitude Learning Speed 📜

### Added

- **5-rank Dao Law system** (`core/dao_laws.py`) — mastery is now shown as
  discrete ranks unlocking at 20/40/60/80/100: Insight 洞察 → Comprehension
  领悟 → Realization 真悟 → Enlightenment 明悟 → Transcendence 超脱. Storage
  stays 0-100 internally; players see "Rank 3 · Realization (61%)" plus
  next-rank progress in `/laws`.
- **Rank resistance (5% → 25%)** — each rank grants **5% damage reduction**
  against attacks of that law's type (Rank 5 = 25%), the curve you asked for.
  **2 ranks ahead = deterministic counter**, no RNG.
- **Aptitude = learning speed** — `/comprehend` insight is now deterministic:
  **`2 + 悟性 ÷ 100`** mastery points, with flat per-source bonuses (secret
  realms +4, tribulations +8, ...). High-悟性 cultivators rank up faster.
- **Migration 016** — re-keys every law's `mastery_effect` ladder to the five
  rank thresholds (with new Rank-5 capstones: `space_dominion`,
  `karmic_justice`, `sword_dominion`, ...) and backfills the legacy milestone
  booleans (now derived from mastery, kept for schema stability).
- **`/law_status` crash fix** — the command referenced `core_items` without
  importing it; it now shows the full rank ladder with per-rank resistance
  instead of crashing.
- **Easier to tune** — every law number (rank thresholds, resistance per rank,
  insight base, source bonuses) is a named constant in `core/dao_laws.py`;
  all law logic consolidated into that one file with a thin cog on top.

### Changed

- `/comprehend` shows rank-up banners instead of milestone banners; the Dao
  Fusion gate message reads Tier 8→9.

### Tests

- Dao Law tests rewritten for ranks/resistance/counter/deterministic insight
  (7 tests) + migration-016 checks. **200 tests passing.**

## [1.5.0] — 2026-08-05 — Stored Qi (存灵气) all-rounder pool 💧

### Added

- **Stored Qi pool** (`core/math.py` + `cogs/cultivation.py`) — a second
  resource separate from dantian Qi, ready to power techniques / artifacts /
  laws when the combat engine lands. Every cultivator rolls a **randomized
  100–300 max** on awakening; a **Chaos Five-Element Root grants +50**.
- **Migration 015** — `stored_qi_current` / `stored_qi_max` /
  `stored_qi_max_bonus` / `stored_qi_regen_bonus` columns with a deterministic
  backfill for existing players, plus three seeded Stored Qi pills.
- **Slow natural regen**: 4/h base, ticked hourly by a new background loop
  (`bot/main.py`); a flat capped regen bonus (+20/h) is the hook pills,
  passives, and techniques will use to speed it up.
- **Stored Qi pills** — `Stored Qi Elixir` (+30), `Stored Qi Concentrate`
  (+80), `Stored Qi Heavenly Dew` (+200), all consumable via `/use`
  (`stored_qi_restore` effect in `cogs/items.py`).
- **Burn-to-continue rules** (`core/math.py`) — the cultivation-base overdraft
  mechanic, fully deterministic: fixed per-realm burn cost table and
  consequences escalating by burn count (3rd → Heart Demon +10%, 5th → forced
  retreat or Qi Deviation, 7th → erasure check on tier 8+). The interactive
  burn button ships with the combat engine.
- **`/profile`** now shows your Stored Qi pool, effective max, and regen rate.
- **PostgreSQL schema** — Stored Qi columns added for parity.

### Tests

- 3 new math tests (awakening roll bounds incl. Chaos Root, regen/restore
  clamps, burn cost + consequence escalation) plus migration-015 checks.
  **197 tests passing.**

## [1.4.0] — 2026-08-05 — 16 Realms × 9 Layers + Transcendence ⛰️

### Added

- **16-realm cultivation ladder** (`core/math.py`) — expanded from 9 tiers × 4
  sub-stages to **16 realms × 9 layers** (144 sub-stages), following the
  "Next Steps" blueprint. Void Refinement (炼虚) was inserted between Soul
  Transformation (化神) and Dao Fusion (合体); the top seven realms ascend
  True Immortal → Golden Immortal → Primordial Chaos → Dao Ancestor → Heavenly
  Venerable → Great Emperor → Beyond Dao (超脱). All Qi/difficulty tables
  (`BASE_QI`, `QI_CAPACITY`, `DIFFICULTY`) were extended exponentially to tier 16.
- **Migration 014** — remaps existing rows onto the new ladder (sub-stages
  1→1 / 2→3 / 3→6 / 4→9; tiers 7–9 shift up one) and adds the Transcendence
  columns (`transcendence_count`, `legacy_passives`,
  `transcendence_capacity_bonus`, `transcendence_qi_gain_bonus`).
- **Transcendence prestige loop** (`/transcend` in `cogs/transcendence.py` +
  pure logic in `core/math.py`) — voluntary endgame prestige at **Beyond Dao
  (16th realm, 9th layer)**, separate from Reincarnation. Resets realm/Qi/Heart
  Demon while permanently stacking: **+15 to all five core stats**, **+5,000 Qi
  capacity** (survives future breakthroughs), **+100 flat Qi per `/cultivate`**,
  an exclusive **Transcendent I/II/III…** title, and one cycling permanent
  passive per cycle. A confirm view guards the irreversible choice.
- **Server blueprint roles** (`core/server_layout.py`) — realm-tier roles now
  mirror all 16 realms (28 → 34 total roles).
- **Item drop grades** (`core/items.py`) — breakthrough loot now scales past
  Heaven: Immortal (tiers 12–14) and God (tiers 15–16) pills and scrolls.
- **PostgreSQL schema** (`migrations/postgres/011_postgres_schema.sql`) — realm
  CHECK widened to 1–16, layer CHECK to 1–9, and the four Transcendence columns
  added for parity.

### Changed

- `next_realm_step` caps at the new summit (16/9); the Dao Fusion gate moved
  from tier 7→8 to tier **8→9**; Heart Demon backlash and Heaven Panel demotes
  now drop to layer 9 instead of sub-stage 4.

### Fixed

- **Transcendence capacity bonus survives erasure & rebirth** — the erasure
  branch (`cogs/cultivation.py`) and reincarnation payload
  (`core/reincarnation.py`) now add `transcendence_capacity_bonus` instead of
  resetting to a plain 1000-capacity vessel.
- **Difficulty curve guard** (`core/math.py`) — an in-realm layer can never be
  harder than the tribulation that leaves the realm, keeping the peak (9th
  layer) the hardest step at every tier.
- **Transcendence confirm view hardening** — double-clicks are answered
  instead of silently failing, and a failed DB write re-enables the buttons
  instead of hanging the interaction.

### Tests

- 6 new tests: realm ladder shape, flat Qi bonus, transcendence payload,
  passive cycling, titles, and a migration-014 remap regression. Blueprint and
  migration counts updated. **194 tests passing.**

## [1.3.0] — 2026-08-05 — The v2 Realm: Full Server Blueprint & Reaction Roles 🏯

### Added

- **Server blueprint v2 (`core/server_layout.py`)** — one source of truth for the whole server, shared by `/setup_server`, the `!setup` fallback, and `scripts/setup_discord_server.py`:
  - **28 roles with real permissions**: 👑 Dao Ancestor (full admin), 🛡️ Heavenly Enforcer, ⚖️ Law Keeper, and 🧹 Sect Steward with graduated moderation permissions; the 9 realm tiers; and 14 self-assignable identity roles (☯️ gender, ⚔️ martial paths, 🌱 element roots, 📖 culture).
  - **8 themed categories / 34 channels** (32 text + 2 voice): Mortal World, Scriptures, Cultivation Grounds, Sects & Bonds, Calamities & Events, Immortal Pavilion, Records & Archives, and a hidden Heavenly Court staff area.
  - **Channel & role permissions**: read-only info channels (mortals read, staff post), hidden staff-only channels, and per-role allow/deny overwrites declared in the blueprint (`channel_overwrites()`).
  - **Rich welcome experience**: 5 auto-posted guides (welcome, rules & commands, getting-started, command reference, role-selection board), pinned where it matters, all idempotent (never duplicated on re-run).
- **Reaction roles (`cogs/reaction_roles.py`)** — members claim their gender/path/root/culture by tapping the role-selection board; exclusive groups auto-swap so every cultivator has exactly one gender, one path, and one root. Emoji→role map lives in `core.server_layout.REACTION_ROLE_MAP` (normalized, no variation-selector drift).
- **Setup logic deduplicated**: the standalone script, the slash command, and the `!setup` fallback all now call the single `apply_server_setup()` builder in `scripts/setup_discord_server.py` — previously the layout-creation logic was copy-pasted three times.
- `validate_layout()` — a pure validator that fails the test suite if the blueprint ever gains duplicates, unknown roles, invalid permission flags, or non-unique channel names.
- Tests: 21 new (`tests/test_server_layout.py`, `tests/test_reaction_roles.py`). Total **188 tests passing**.

### Fixed

- **Migration 013 (`013_guild_config_announcement.sql`)**: `guild_config.announcement_channel_id` only ever existed in the PostgreSQL schema — the SQLite setup flow (which persists the announcements channel) would crash with `no such column` at runtime. SQLite now gains the column; the migration runner tolerates a re-run.
- **`create_voice_channel` no longer receives `topic`** — this discord.py version doesn't accept it, and passing it would have TypeError'd the whole setup at the first voice channel.
- **Channel creation is now server-wide aware**: Discord enforces unique channel names across the guild, so setup reuses a same-named channel anywhere rather than crashing with a 400.
- **Guide idempotency hardened**: duplicate-guide detection now scans pinned messages + 100 messages of history, and the role-selection board repairs missing reactions on re-run.
- **Standalone setup client reports errors cleanly** instead of dying with a raw traceback.

## [1.2.0] — 2026-08-05 — Off-Server Disaster Recovery & Deployment Docs 🛡️

### Added

- **Off-server GitHub backup mirror** (`scripts/github_backup.py`): every daily SQLite snapshot in `backups/` is now pushed to a dedicated `db-backups` branch in a GitHub repository via the Contents API (`aiohttp` — no new dependencies, no git install needed on the host). Configurable via `GITHUB_BACKUP_TOKEN` / `GITHUB_BACKUP_REPO` / `GITHUB_BACKUP_BRANCH` / `GITHUB_BACKUP_KEEP` in `.env` (best-effort — logs "mirror skipped" when unconfigured). Wired into the daily `backup_loop` (`bot/main.py`); the branch is auto-created from the default branch and old snapshots are pruned automatically (newest 14 kept by default). Tested end-to-end against a fake GitHub API.
- **`DEPLOY_WISPBYTE.md`** — full free 24/7 hosting guide for wispbyte: panel setup (Python image, free plan), SFTP upload layout, the complete `.env`, startup command, first-boot verification checklist, daily operations, and troubleshooting.

### Fixed

- **README project-layout drift**: `db/sqlite.py` → `db/database.py`, `config/settings.py` → `config/default.py`, migration list now includes 012 (both `migrations/` and `migrations/postgres/`), and the test count was updated from the stale 119.
- Tests: 7 new (`tests/test_github_backup.py`). Total **167 tests passing**.

## [1.1.0] — 2026-08-04 — Spiritual Aptitudes & Martial Intent Engine 🎉

### Fixed — Auction House seller commands completed (`cogs/auction.py`)

- `/my_listings` and `/cancel_listing` were listed in the v1.0.0 changelog and README but were **not actually implemented** — they only existed as references in the cog docstring, `/help` text, and setup script. Both are now live:
  - `/my_listings` — review of your active market listings (price, top bid, buyout, expiry).
  - `/cancel_listing <id>` — cancels an active listing: refunds the 5% listing fee, returns the item to your `/inventory`, and releases any escrowed bid back to the current bidder. Validated by the new `validate_cancel_listing()` in `core/auction.py`, and the cancel is claimed via an atomic guarded `UPDATE ... WHERE status='active' AND seller_id=?` + rowcount check so a concurrent `/buy` or a crash-retry can never double-refund.
- **Listings now actually expire**: `/sell` previously ignored `duration_hours` and set `expires_at` to the present moment. It now writes a real expiry timestamp (clamped 1–168h via `clamp_listing_duration()` in `core/auction.py`; `future_str()` in `bot/utils.py`), and a new `market_expiry_loop` background task (every 60s) sweeps due listings: atomically marks them `expired`, refunds any escrowed bid to the bidder, and returns the item to the seller. Same guarded-UPDATE + rowcount pattern so a concurrent `/buy` or `/cancel_listing` cannot double-refund.
- **Fixed pre-existing SQL column bug**: the auction cog and `db/queries.py` queried `items.item_name`, but the column is `name` — `/sell`, `/buy`, `/trade`, and `/trade_accept` would have crashed at runtime with `no such column`. All market/trade queries now select `i.name AS item_name`.
- **Hardened `/buy` and `/bid` against expiry/cancel races**: both now atomically claim the listing first (guarded `UPDATE ... WHERE status='active'` + rowcount) before any stones or items move, so a concurrent expiry sweep or `/cancel_listing` can no longer interleave mid-transaction (previously a buyer could pay while a sweep returned the item to the seller).
- Tests: 1 new clamp test (`tests/test_auction.py`) + 1 end-to-end expiry-sweep integration test (`tests/test_integration.py`). Total 160 tests passing.

### Added — Spiritual Aptitudes & Martial Intent Engine (`core/affinities.py` & `cogs/affinities.py`)

- **Migration 012 (`012_spiritual_aptitudes.sql`)**: Adds 12 columns to `cultivators` for Five Phases affinities (`affinity_fire`, `affinity_water`, `affinity_wood`, `affinity_metal`, `affinity_earth`, `affinity_qi`), Martial Weapon Intents (`intent_sword`, `intent_sabre`, `intent_spear`, `intent_fist`), Yin-Yang alignment (`yin_yang_balance`), and special root (`special_root`).
- **Aptitude Awakening & Mechanics (`core/affinities.py`)**:
  - **Randomized Awakening**: Initial 60-point element pool (max 25/stat) and 30-point intent pool (max 15/stat) assigned automatically on `/register`.
  - **1% Chaos Root**: Rare chance on registration for high-tier balanced elemental roots (20-25 per stat).
  - **Stat Multipliers**:
    - **Fire**: +Crit Chance & +Crit Damage.
    - **Water**: +Evasion, +Speed & +Vitality Recovery.
    - **Wood**: +Debuff Immunity.
    - **Metal**: +Armor Penetration & +Raw Damage.
    - **Earth**: +CC Resistance & +Barrier Shielding.
    - **Qi**: +Qi Regen Speed, +Qi Gain & +Dantian Efficiency.
    - **Yin/Yang Balance**: +Yang Fortitude or +Yin Heavenly Tribulation Resistance.
    - **Martial Intents**: +Multi-hit, +Cleave Damage, +Lifesteal, +Counter-attack, +Armor Break, +Dantian Damage.
- **Commands & Server Setup (`cogs/affinities.py` & `cogs/dao_config.py`)**:
  - `/aptitudes` — Displays player's complete Spiritual Root profile, Five Phases, Martial Intents, Yin-Yang balance, and active stat multipliers.
  - `/setup_server` — Admin-only slash command to automatically create all server categories, channels, roles, welcome guides, and database `guild_config`.
- **Equipment Prerequisite Validation (`core/items.py`)**: High-tier weapons and scrolls validate player aptitudes before equipping.
- **Tests**: Added 35 unit tests in `tests/test_affinities.py`. Total test count: 154 passing.

## [1.0.0] — 2026-08-04 — Official 1.0 Release! 🎉

Phase 4 — PostgreSQL Migration Path (Step 4 - Capstone Release).

### Added — PostgreSQL Migration Path & Enterprise Infrastructure

- **Consolidated PostgreSQL Schema** (`migrations/postgres/011_postgres_schema.sql`): Consolidated DDL for PostgreSQL 15+ featuring native `JSONB`, `uuid-ossp`, GIN indexing, and `PARTITION BY RANGE` for `qi_buffer` and `audit_log`.
- **Async PostgreSQL Pool Layer** (`db/postgres.py`): Enterprise connection pooling using `asyncpg` with zero-downtime config switching (`config/postgres.py`).
- **Automated Data Migration Script** (`scripts/migrate_sqlite_to_postgres.py`): One-way migration utility executing automated JSON deserialization and batch inserts from SQLite to PostgreSQL.
- **Migration Parity Validator** (`scripts/validate_migration.py`): Verification tool confirming table row count parity and schema integrity post-migration.
- **Operations & Deployment Guide** (`MIGRATION.md`): Step-by-step documentation detailing PostgreSQL provisioning, data transfer, zero-downtime cutover, and emergency rollback procedures.
- Tests: 3 new unit tests (`tests/test_postgres.py`). Total 119 tests passing across all 12 system phases!

Phase 4 — Auction House & P2P Trading System (Step 3).

### Added — Auction House & P2P Trading (`core/auction.py` & `cogs/auction.py`)

- **Migration 010** adds `market_listings` table (seller_id, item_id, quantity, price, buyout_price, current_bid, current_bidder_id, status) and `trade_offers` table (sender_id, recipient_id, item_id, quantity, status).
- Deterministic Auction Engine (`core/auction.py`):
  - **Listing Fees & Sales Tax**: Enforces 5% upfront listing fee (min 1 stone) and 5% market tax deducted from seller proceeds upon purchase.
  - **Bidding Rules**: Enforces 10% minimum increment over current bid and holds bidder spirit stones in escrow with auto-refund for previous bidders.
  - **Active Listing Limits**: Caps active listings at 5 per cultivator.
  - **P2P Direct Trade**: Enables direct item trade proposals with 10-minute expiry window.
- Slash Commands (`cogs/auction.py`):
  - `/market` — Browse active market listings with paginated view.
  - `/sell <item_name> <price>` — List owned item on market (5% listing fee, optional buyout price).
  - `/buy <listing_id>` — Instant buy item at buyout/listed price (transfers item & credits seller after 5% tax).
  - `/bid <listing_id> <amount>` — Place a bid on an active listing (+10% min increment).
  - `/my_listings` — View your active market listings and top bids.
  - `/cancel_listing <listing_id>` — Cancel an active listing and return item to inventory.
  - `/trade @user <item_name>` — Send direct P2P trade offer to another cultivator.
  - `/trade_accept` / `/trade_decline` — Accept or decline pending trade offers.
- Tests: 6 new pure-logic unit tests (`tests/test_auction.py`). Total 116 tests passing.

Phase 4 — Dao Laws Endgame System (Step 2).

### Added — Dao Laws System (`core/dao_laws.py` & `cogs/dao_laws.py`)

- **Migration 009** adds `dao_laws` catalog (seeded with 5 Fundamental Laws: `Law of Space`, `Law of Time`, `Law of Karma`, `Law of Sword`, `Law of Alchemy`) and `cultivator_laws` junction table.
- Deterministic Dao Laws Engine (`core/dao_laws.py`):
  - **Insight Sources**: Computes mastery insight gains from `/comprehend` (1-3%), secret realms (2-5%), tribulations (5-10%), world bosses (1-2%), ancient texts (1-3%), and sect meditation (0.5-1%).
  - **4 Milestone Thresholds**: Tracks milestone unlocks at 25% (First Vision), 50% (Technique Unlock), 75% (Dao Resonance), and 100% (Complete Mastery).
  - **Effect Aggregation**: Resolves cumulative damage bonuses, dodge bonuses, breakthrough bonuses, and unlocked passive techniques across all mastered laws.
  - **Dao Fusion Gate**: Enforces 100% Law Mastery requirement in at least one law for Tier 7→8 Dao Fusion breakthrough (`cogs/cultivation.py`).
- Slash Commands (`cogs/dao_laws.py`):
  - `/laws` — Overview of fundamental laws, current mastery percentages, and active milestones.
  - `/comprehend <law_name>` — Meditate on a law to gain insight (4-hour cooldown, 100 Qi cost).
  - `/law_status <law_name>` — Inspect law lore, requirements, and milestone effects.
- Tests: 5 new pure-logic unit tests (`tests/test_dao_laws.py`). Total 110 tests passing.

Phase 4 — World Events & Heavenly Calamities (Step 1).

### Added — World Events System (`core/world_events.py` & `cogs/world_events.py`)

- **Migration 008** adds `world_events`, `world_event_participants`, and `world_event_phases` tables.
- Deterministic World Events Engine (`core/world_events.py`):
  - **Damage Formula**: `damage = (strength * 8 + spirit * 4 + weapon_bonus) * technique_mult * sect_array_bonus * (1 + law_mastery / 1000) * rng_factor`.
  - **5-Phase Boss Progression**: Smooth phase transitions (`Normal` → `Enraged` → `Minions` → `Desperation` → `Final Stand`) with status narratives.
  - **Sect Sacrifice Buffs**: Patriarch treasury stone sacrifices granting party-wide damage buffs (up to +50%), healing over time, and debuff immunity.
  - **Event Rewards**: Tiered reward packages based on damage leaderboard ranking (Unique titles, God/Immortal/Heaven grade loot, spirit stones).
- Slash Commands (`cogs/world_events.py`):
  - `/events` — List active and scheduled world calamities.
  - `/event_join <event_id>` — Register participation in a World Boss event.
  - `/event_attack <event_id>` — Strike active World Bosses, dealing damage and progressing HP/phases.
  - `/event_status <event_id>` — Check Boss HP bar, narrative state, and damage leaderboard.
  - `/event_claim <event_id>` — Claim post-event loot rewards based on damage rank.
  - `/spawn_event <type>` — Admin command to schedule/spawn new server World Events.
- Tests: 5 new pure-logic world event tests (`tests/test_world_events.py`). Total 105 tests passing.

Phase 3 — Secret Realms & Groq Integration (Step 4 & Step 5).

### Added — Secret Realms System (`core/secret_realms.py` & `cogs/secret_realms.py`)

- **Migration 007** adds `secret_realm_templates` catalog (seeded with `Ancient Sword Tomb`, `Emerald Herb Valley`, `Dragon Blood Cavern`) and `secret_realm_runs` table for player dungeon runs.
- Deterministic Secret Realms Engine (`core/secret_realms.py`):
  - **Node Encounter Generator**: Generates branching dungeon depth nodes (`Monster`, `Treasure`, `Trap`, `Herb_Garden`) with difficulty scaling and Guardian Boss nodes at final depths.
  - **Stat-based Resolution**: Resolves player choices against difficulty using Physique/Spirit for combat, Luck for traps, and Comprehension for herbs.
  - **Loot & Run Progression**: Accumulates loot across nodes, supports safe retreat (`/retreat`), and grants all collected items upon dungeon completion.
- Slash Commands (`cogs/secret_realms.py`):
  - `/realms` — List available secret realm dungeons, minimum realm requirements, and potential drops.
  - `/enter_realm <realm_name>` — Open portal and enter a secret realm (deducts Qi cost).
  - `/explore` — Explore the next encounter node with interactive action buttons (`[ Fight / Proceed ]`, `[ Evade / Disarm ]`).
  - `/retreat` — Leave the portal safely keeping all accumulated loot collected so far.
- Groq Tier-4 Integration (`core/groq_client.py`):
  - `generate_or_template()` wired for LLM narrative flavoring with seamless fallback to `TemplateEngine`.
- Tests: 5 new pure-logic secret realm tests (`tests/test_secret_realms.py`). Total 100 tests passing.

Phase 3 — Reincarnation System ("Death Is Not The End", Step 3).

### Added — Reincarnation System (`core/reincarnation.py` & `cogs/reincarnation.py`)

- **Migration 006** adds `inherited_technique` and `reincarnation_breakthrough_bonus` to `cultivators`, plus `reincarnation_log` table for tracking past life cycles.
- Deterministic Reincarnation Engine (`core/reincarnation.py`):
  - **Legacy Retention**: Retains 25% Comprehension, 10% Luck, 50% unspent stat points, and 1 inherited technique scroll on rebirth.
  - **Cycle Progression**: Stacking +5% breakthrough success bonus per cycle (max +25%) and unique reincarnated physiques (`Mortal Meridian` → `Reincarnated Soul` → `Twice-Born Dao Heart` → ... → `Heavenly Dao Reject`).
  - **Template Epitaphs & Memories**: Automatic epitaph generation and past life memory unlocks at Comprehension 100, 250, 500, 1000 thresholds.
- Slash Commands (`cogs/reincarnation.py`):
  - `/reincarnate` — Interactive voluntary rebirth for Nascent Soul (Tier 5+) with half-full dantian and confirmation UI.
  - `/past_lives` — View reincarnation log history, epitaphs, retained techniques, and past-life memory unlocks.
  - `/legacy` — Live preview of retained stats, bonuses, techniques, and next physique.
- Integration: Heavenly Dao Erasure at Tier 8+ now triggers legacy-preserving rebirth rather than raw reset (`cogs/cultivation.py`).
- Tests: 7 new pure-logic unit tests (`tests/test_reincarnation.py`). Total 95 tests passing.

Phase 3 — Alchemy Mini-Game (Step 2).

### Added — Alchemy System (`core/alchemy.py` & `cogs/alchemy.py`)

- **Migration 005** adds `alchemy_mastery`, `alchemy_fame`, and `equipped_cauldron` to `cultivators`, plus `alchemy_recipes` catalog (seeded with 4 pill recipes) and `alchemy_attempts` log table.
- Deterministic Alchemy Engine (`core/alchemy.py`):
  - **3-Stage Mini-Game Scoring**: Fire Control pattern accuracy (1-10), Ingredient Order sequence check (1-10), and Spiritual Sense comprehension roll (1-10).
  - **Success Rate Math**: `calculate_success_rate` factoring base rate, mastery (+2%/lvl), cauldron bonus, and mini-game stage scores, clamped to [5%, 95%].
  - **Result Roll & Effects**: Miracle (1% chance for 1.5x effect multiplier), Success (pill granted), Failure (+1% Heart Demon), and Cauldron Explosion (25% Qi loss + 5% Heart Demon).
- Slash Commands (`cogs/alchemy.py`):
  - `/recipes [grade]` — List known recipes with required ingredients, difficulty, and output effects.
  - `/alchemy_status` — View mastery level, equipped cauldron, fame, and recent refinement history.
  - `/refine_pill <recipe_name>` — Interactive 3-stage mini-game with live Fire Control buttons and Ingredient Select Menus. Grants +1 alchemy mastery per attempt.
- Tests: 21 new pure-logic alchemy tests (`tests/test_alchemy.py`). Total 88 tests passing.

Phase 3 — Inventory & Items System (Step 1).

### Added — Inventory & Items (`core/items.py` & `cogs/items.py`)

- **Migration 004** adds `is_equipped` and `equipped_slot` columns to `items`, plus an `item_templates` catalog seeded with Pills, Weapons, Technique Scrolls, Talismans, and Materials.
- Deterministic Item Engine (`core/items.py`):
  - **Effect Data Parser**: JSON-based effects (`qi_boost`, `stat_buff`, `breakthrough_aid`, `heart_demon_purge`, `protection`).
  - **Equipment Manager**: Enforces equipment limits (max 1 Weapon and max 1 Technique Scroll). Passive stat buffs and breakthrough success bonuses from equipped items automatically apply to cultivation loops.
  - **Drop Tables**: Breakthrough success drops (Protection Charms 5%, Pills 15%, Technique Scrolls 8%) and cultivate daily streak drops (Materials 20%, Talismans 10%).
- Slash Commands (`cogs/items.py`):
  - `/inventory [page]` — Paginated spatial ring display of items with equipped markers.
  - `/equip <item_name>` — Equip/unequip weapons or technique scrolls.
  - `/use <item_name>` — Consume pills, talismans, or charms (applies instant Qi, purges Heart Demon, or grants protective charms).
  - `/give @user <item_name> [quantity]` — Trade items with other cultivators in the server.
  - `/item_info <item_name>` — View grade, lore, type, and parsed effect breakdown.
- Tests: 5 new pure-logic item tests (`tests/test_items.py`) verifying parsing, drop rates, equip constraints, and equipment bonuses. Total 67 tests passing.

Phase 2 — Sects & Spirit Stone Economy.

### Added — Sects (Phase 2 social: player-run organizations)

- **Migration 003** adds a personal `spirit_stones` wallet to `cultivators`
  (earned at **+10 per successful breakthrough**), plus a ranking index for
  leaderboard-style stone displays.
- Deterministic sect engine (`core/sects.py`):
  - **Five-rank hierarchy** — Outer Disciple → Inner Disciple → Core Disciple →
    Elder → Patriarch. Patriarchs promote (one step at a time, never past their
    own rank) or demote (any member below them, not below Outer Disciple).
  - **Array upgrade economy** — exponential cost `int(500 × 1.5^(level-1))`,
    capped at level 7 (+56%, matching the existing `ARRAY_BONUS_CAP` of +50%).
  - **Creation gate** — only Foundation Establishment (tier 3+) cultivators may
    found a sect; name must be 2–40 chars.
  - **Join/leave** — free agents join as Outer Disciples (respecting `max_members`);
    a Patriarch leaving **disbands** the sect (all members go sectless).
- New commands (`cogs/sects.py`):
  - `/sect_create <name>` — found a sect, become Patriarch.
  - `/sect_join <name>` — join as Outer Disciple.
  - `/sect_leave` — leave; Patriarch departure disbands.
  - `/sect_info [name]` — dashboard: patriarch, member count/max, array level &
    bonus, treasury, next-upgrade cost, top-15 roster.
  - `/sect_donate <amount>` — give spirit stones from your wallet to the treasury.
  - `/sect_upgrade_array` — Patriarch spends treasury on the next array level.
  - `/sect_promote @user` — promote one rank step (Patriarch only).
  - `/sect_demote @user` — demote (Patriarch only).
  - `/sect_expel @user` — expel a member of lower rank (Patriarch only).
- `/breakthrough` success now awards spirit stones and shows them in the reward
  field; `/profile` now displays the spirit-stone balance.
- **Language Mode Toggle** — `/dao_config` now supports selecting between `english` (Pure English UI) and `bilingual` (English + Chinese flavor text). Pure English mode renders clean English embed headers, stat names (`Physique`, `Spirit`, `Luck`, `Comprehension`), realm labels (`Foundation Establishment (Mid)`), and dantian Qi units.
- New query helpers in `db/queries.py`: `sect_by_name`, `sect_members`,
  `sect_member_count`.
- Tests: 19 new pure-logic tests (sects rank hierarchy, cost scaling, language formatting) + migration-003 updates.

## [0.2.0] — 2026-08-04

Phase 2 — Dao Bonds (companions are real people).

### Added — Dao Bonds (review v2 pivot: companions are real people)

- **Minimum realm gate** — Mortals (tier 1) may no longer form Dao Bonds; both
  players must have reached **Qi Condensation (炼气, tier 2)** or higher. Enforced
  in `validate_bond_formation` with a clear rejection message.
- **Fickle rebond stigma** — a severer who proposes a *new romantic bond*
  (道侣 Dao Companion / 双修 Dual Cultivation Partner) within **7 days** of
  breaking the old one is branded **薄情寡义 Fickle Heart** (visible on
  `/profile`) and named publicly in the proposal embed. Victims are exempt.
  This is the intended seed for the demonic-cultivation path (Phase 3).
- New `dao_bonds` table (migration 002): player-to-player relationship graph
  with a unique per-pair index (one bond per pair, any direction), status
  lifecycle (`forming` → `active` → `severed`), bond tier (1–20) & points,
  shared-event history, and dual-cultivation tracking.
- Deterministic bond engine (`core/dao_bonds.py`):
  - **Gender matrix** — same-gender pairs cannot form romantic bonds; both
    players must hold a gender role mapped via `/dao_config`
    (`dao_male_role` / `dao_female_role`, stored per-guild).
  - Realm-gap rules (romantic within 1 realm, standard up to 3, master 2+
    realms above disciple) and polygamy limits (3 companions / 1 dual partner /
    5 sworn siblings / 3 disciples / 1 rival / 10 sect siblings).
  - Real-stat synergy formula (complementary stats + karma alignment ×1.2/×0.7
    + realm proximity + bond tier), bond-tier progression from points.
  - Severance drama: Heart Demon for both (tier × 5%), −100 karma for the
    betrayer, victim gains **Betrayed** title + 7-day +15% rage cultivation
    buff (new `rage_breakthrough_bonus_until` column; wired into the
    breakthrough probability).
- New commands: `/dao_bond`, `/dao_bond_accept`, `/dao_bond_decline`,
  `/dao_bond_sever` (public announcement), `/dao_bonds`, and `/dual_cultivate`
  with a two-player consent ritual (bond tier 3+, 4h cooldown, Qi burst +
  Heart Demon reduction + bond points for both).
- `/profile` now shows active Dao Bond count instead of the NPC companion count.
- Tests: 11 new Dao Bond tests (gender matrix, realm gaps, limits, synergy,
  severance, rage, gender-map parsing) + migration updates.

### Planned

- **Phase 2 (social):** sects, master–disciple bonds, Dao Companions/harem,
  inventory & items
- **Phase 3 (advanced):** alchemy mini-game, karma reincarnation, secret
  realms, Groq Tier-4 wiring
- **Phase 4 (world):** full world-event mechanics, Dao Laws endgame, auction
  house / P2P trading, PostgreSQL migration

## [0.1.0] — 2026-08-04

Phase 1 — foundation & the core cultivation loop.

### Added

- Discord bot scaffold (Python 3.12, discord.py 2.7, aiosqlite, WAL mode,
  `MESSAGE CONTENT INTENT` for passive Qi).
- Versioned migration runner (`migrations/*.sql`, tracked in
  `schema_migrations`) and a narrative-template seed loader
  (`templates/*.json`).
- SQLite schema adapted from the v2.0 blueprint with **all Kimi-review P0
  fixes**: surrogate PKs + `UNIQUE(guild_id, user_id)`, append-only
  `qi_buffer`, `qi_hourly_stats`, per-guild `guild_config`, anti-cheat flags,
  world events + participants, protection charms, breakthrough log, LLM usage
  log, and every review-suggested index.
- Core loop commands: `/register`, `/cultivate`, `/breakthrough`, `/allocate`,
  `/profile`, `/leaderboard`.
- Passive Qi from chat: 15 messages/hour cap, <5-char and 60s-repeat
  anti-spam, channel blacklist/whitelist, memory-buffered batch flush (60s)
  into the append-only `qi_buffer`.
- Balance engine (deterministic): exponential breakthrough difficulty
  (15 → 1886), non-linear Heart Demon penalty, Karma ±10%, sect array bonus,
  Dao Mercy pity (+5% per failed attempt, capped at +25%), success clamped to
  5–95%.
- Heavenly Dao Erasure (0.5% on tier-8+ **failures**) with three charm
  counterplays (karmic shield / reincarnation seed / dao heart anchor) and
  "never account death" legacy retention (25% comprehension, 10% luck,
  Ashen Remnant title).
- Admin `/heaven_panel` (ephemeral): server stats, Qi throughput, anti-cheat
  review, and one-click Dao Punish / Dao Bless / Spawn Event / Broadcast
  flows. `/dao_config` for per-guild settings.
- Template engine (Tier-2, zero LLM cost) seeded with ~100 bilingual
  narrative fragments.
- Optional Groq free-tier client (Tier-4, **disabled by default**): 1 call /
  player / 24h, 10/hour and 100/day global, fail-closed with template
  fallback.
- Background tasks: presence loop, daily DB snapshot backup, world-event
  scheduler (activates due calamities).
- Test suite (24 tests): balance math, anti-spam rules, migration
  idempotency, per-guild uniqueness, template engine, Groq fail-closed,
  buffered-Qi end-to-end pipeline.
- Documentation: `README.md`, `MIGRATION.md`, this changelog, and an
  annotated `.env.example`.

### Fixed

- **Max-tier regression** — `next_realm_step(9, 4)` no longer drops an
  Immortal Peak cultivator's sub-stages; advancement caps at the summit.
- **Erasure Qi semantics** — charm refunds now apply to the post-failure
  (halved) Qi, keeping the 50% failure penalty invariant and making the three
  charms consistent.
- **Passive-Qi race** — the hourly cap and repeat-tracking are persisted
  before awaits so interleaved handlers can no longer exceed 15 msgs/hour.
- **IntegrityError race** — `get_or_create_cultivator` recovers when a
  concurrent first interaction hits the unique index.
- **Panel privacy** — `/heaven_panel` is ephemeral; flagged users and server
  stats are no longer broadcast to the channel.
- **Task readiness** — background loops wait for the gateway before their
  first run.
