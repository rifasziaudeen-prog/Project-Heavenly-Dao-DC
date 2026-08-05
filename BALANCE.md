# ⚖️ Heavenly Dao — Tuning Sheet (BALANCE.md)

**Every game number lives in ONE named constant, in ONE file, per system.**
This sheet is the map: find the knob you want to change → open the file →
edit the constant → restart the bot. No hunting, no percentages hidden in
embeds, no magic numbers. Line numbers drift as the code grows — **search by
constant name** (most editors: `Ctrl+F`).

> Golden rule: never edit numbers inside `cogs/*.py` embed text or SQL seeds
> if a constant already exists for it. Core files are the source of truth.

---

## 1. Realms & Qi — `core/math.py`

| What it does | Constant | Current |
|---|---|---|
| Realm names (16 realms) | `REALMS` | Qi Condensation → Beyond Dao |
| Layer names (9 layers per realm) | `LAYERS` | First Layer → Ninth Layer |
| Realm count | `MAX_TIER` | `16` |
| Layers per realm | `MAX_LAYER` | `9` |
| Qi gained per `/cultivate` per realm | `BASE_QI` | per-realm table |
| Qi capacity (how much you can hold) | `QI_CAPACITY` | per-realm table |
| Qi multipliers per activity | `SOURCE_MULT` | chat / secret realm / etc. |
| Companion boost cap | `COMPANION_BONUS_CAP` | `2.0` (max 2×) |
| Sect array boost cap | `ARRAY_BONUS_CAP` | `0.50` (max +50%) |

## 2. Breakthrough — `core/math.py`

| What it does | Constant | Current |
|---|---|---|
| Difficulty per realm (denominator of chance) | `DIFFICULTY` | per-realm table |
| Difficulty rise between layers | `SUB_STAGE_DIFFICULTY_FACTOR` | `0.125` |
| **Dao Mercy**: +% chance per failed attempt | `MERCY_PER_FAILURE` | `0.05` (+5%) |
| Dao Mercy cap | `MERCY_CAP` | `0.25` (+25%) |
| Chance to find a charm on breakthrough | `CHARM_DROP_CHANCE` | `0.05` (5%) |
| Charm types | `CHARM_TYPES` | karmic_shield, reincarnation_seed, dao_heart_anchor |

## 3. Heavenly Dao Erasure — `core/math.py`

| What it does | Constant | Current |
|---|---|---|
| Erasure chance per failed tribulation (tier 8+) | `ERASURE_CHANCE` | `0.005` (0.5%) |
| Minimum tier where erasure can trigger | `ERASURE_MIN_TIER` | `8` |

## 4. Heart Demon — `core/math.py`

| What it does | Constant | Current |
|---|---|---|
| Visible point scale (0–X) | `HD_POINTS_MAX` | `20` |
| Penalty curve (non-linear) | `heart_demon_penalty()` | uses ratio¹.⁵ |

Heart Demon is stored internally as a 0–1.0 ratio but shown to players as
**0–20 points** (`X/20`). One point = `0.05` ratio. Duel losses, defeats,
and alchemy explosions add points from the engine constants listed in each
system below.

## 5. Stored Qi · 存灵气 — `core/math.py`

| What it does | Constant | Current |
|---|---|---|
| Randomized starting max range | `STORE_QI_MIN` / `STORE_QI_MAX` | `100` – `300` |
| Chaos Root bonus to max | `STORE_QI_CHAOS_BONUS` | `+50` |
| Natural regen per hour | `STORE_QI_BASE_REGEN` | `4` |
| Extra regen cap from pills/passives | `STORE_QI_REGEN_BONUS_CAP` | `20` |
| Burn-to-continue dantian cost per realm | `STORE_QI_BURN_COST` | per-realm table |

## 6. Transcendence — `core/math.py`

| What it does | Constant | Current |
|---|---|---|
| Transcendence realm/layer | `TRANSCENDENCE_REALM` / `_LAYER` | 16 / 9 |
| Base Qi capacity at transcendence | `TRANSCENDENCE_BASE_CAPACITY` | `1_000` |
| Permanent stat bonus (all five stats) | `TRANSCENDENCE_STAT_BONUS` | `+15` |
| Permanent Qi capacity bonus | `TRANSCENDENCE_QI_CAPACITY_BONUS` | `+5_000` |
| Permanent passive gifts | `TRANSCENDENCE_PASSIVES` | list |

## 7. Contendance Combat — `core/combat.py`

| What it does | Constant | Current |
|---|---|---|
| HP per realm (duel/battle pool) | `HP_MAX` | 120 → 2,200 |
| Dao Heart max / loss per lost clash | `DAO_HEART_MAX` / `DAO_HEART_LOSS_PER_CLASH` | `100` / `10` |
| Technique mastery ranks unlock at | `TECHNIQUE_RANK_THRESHOLDS` | 20/40/60/80/100 |
| Mastery gained per technique use | `TECHNIQUE_MASTERY_PER_USE` | `+2` |
| Damage per rank above 1 | `TECHNIQUE_RANK_DAMAGE` | `+3` |
| Stored Qi cost reduction per rank | `TECHNIQUE_RANK_COST_REDUCTION` | `-5` |
| Cheapest a technique can cost | `TECHNIQUE_MIN_COST` | `5` |
| Unfold-a-law Stored Qi cost | `LAW_UNFOLD_COST` | `30` |
| Artifact parry Stored Qi cost | `ARTIFACT_COST` | `10` |
| Round window (duels) | `INTENT_WINDOW_SECONDS` | `20` |
| Max duel rounds | `MAX_DUEL_ROUNDS` | `30` |
| Artifact parry base / cap | `ARTIFACT_PARRY_BASE` / `_CAP` | `10` / `40` |
| Burn grants Stored Qi / costs Dao Heart | `BURN_STORED_QI_GAIN` / `BURN_DAO_HEART_COST` | `+100` / `10` |

**Technique entries** (rolled at learn time, same file):
`ENTRY_POOL` (Afterimage, Penetration, Overcharge, Karmic Weight),
`ENTRY_MIN_ROLL` / `ENTRY_MAX_ROLL` (`1`–`3` entries).

**Spirit beasts** (`/battle`): `SCRIPTED_BEASTS` — each beast's realm, HP,
scripted intent pattern, stone reward, and technique-drop chance.

## 8. Dao Laws — `core/dao_laws.py`

| What it does | Constant | Current |
|---|---|---|
| 5 ranks unlock at mastery | `LAW_RANK_THRESHOLDS` | 20/40/60/80/100 |
| Resistance per rank (5% → 25%) | `LAW_RESISTANCE_PER_RANK` | `0.05` |
| Insight per `/comprehend` (悟性 base) | `LAW_INSIGHT_BASE` | `2` |
| Flat insight from other sources | `INSIGHT_SOURCE_FLAT` | secret realm +4, tribulation +8, etc. |

The 5 laws (Space/Time/Karma/Sword/Alchemy) live in the DB seed:
`migrations/009_dao_laws.sql` (their mastery effects too).

## 9. Sects — `core/sects.py`

| What it does | Constant | Current |
|---|---|---|
| Minimum realm to found a sect | `SECT_CREATE_MIN_TIER` | `3` |
| Max name length | `SECT_MAX_NAME_LENGTH` | `40` |
| Max array level | `SECT_MAX_ARRAY_LEVEL` | `7` |
| Array upgrade cost base (×1.5 per level) | `ARRAY_UPGRADE_BASE_COST` | `500` |
| Spirit stones per breakthrough | `SPIRIT_STONES_PER_BREAKTHROUGH` | `10` |
| **Array burst** cost (level 1) | `ARRAY_BURST_BASE_COST` | `500` |
| Array burst cost per extra level | `ARRAY_BURST_COST_PER_LEVEL` | `250` |
| Array burst Stored Qi pulse (level 1) | `ARRAY_BURST_BASE_PULSE` | `30` |
| Array burst pulse per extra level | `ARRAY_BURST_PULSE_PER_LEVEL` | `10` |
| Array burst cooldown | `ARRAY_BURST_COOLDOWN` | `6` hours |

## 10. World-boss Contendance — `core/world_events.py`

| What it does | Constant | Current |
|---|---|---|
| Boss scripted intent patterns | `BOSS_INTENT_PATTERNS` | per event type |
| Boss unfold law + rank | `BOSS_UNFOLD_LAW` / `BOSS_UNFOLD_RANK` | Law of Sword / 1 |
| Boss strike power per phase | `BOSS_PHASE_POWER` | 18 → 24 → 30 → 38 → 48 |
| Combat damage → boss HP bar | `BOSS_DAMAGE_SCALE` | `30` |
| Your HP regen per hour away | `BOSS_HP_REGEN_PER_HOUR` | `20` |
| Defeat penalty (Heart Demon) | `BOSS_DEFEAT_HD_RATIO` | `0.05` (+1 Point) |
| Defeat recovery minutes | `BOSS_DEFEAT_COOLDOWN` | `30` |
| Pill heal on the battlefield | `BOSS_PILL_HEAL` | `25` |
| Event rewards table | `calculate_event_rewards()` | ranks 1–10+ packages |

## 11. Dao Bonds — `core/dao_bonds.py`

| What it does | Constant | Current |
|---|---|---|
| Minimum realm for bonds | `MIN_REALM_TIER` | `2` |
| Romantic realm gap / other gap | `ROMANTIC_REALM_GAP` / `STANDARD_REALM_GAP` | 1 / 3 |
| Master must be N realms higher | `MASTER_TIER_DIFFERENCE` | `2` |
| Bond limits per type | `BOND_LIMITS` | e.g. 1 master |
| Dual cultivation cooldown | `DUAL_COOLDOWN_HOURS` | `4` |
| Dual cultivation Qi bonus cap | `DUAL_QI_BONUS_CAP` | `2.0` |
| Dual cultivation Heart Demon reduction | `DUAL_HEART_DEMON_REDUCTION` | `0.03` |
| Bond points per dual cultivate | `DUAL_BOND_POINTS` | `50` |
| Points per bond tier | `BOND_TIER_POINT_THRESHOLD` | `250` |
| Severance Heart Demon per tier | `SEVER_HEART_DEMON_PER_TIER` | `0.05` |
| Betrayer karma loss | `SEVER_BETRAYER_KARMA` | `-100` |
| Rage buff days / breakthrough bonus | `RAGE_BUFF_DAYS` / `RAGE_BREAKTHROUGH_BONUS` | 7 / 0.15 |

## 12. Aptitudes & Martial Intents — `core/affinities.py`

| What it does | Constant | Current |
|---|---|---|
| Element points on awakening | `ELEMENT_POOL` | `60` |
| Max one element can roll | `ELEMENT_MAX_SINGLE` | `25` |
| Intent points on awakening | `INTENT_POOL` | `30` |
| Max one intent can roll | `INTENT_MAX_SINGLE` | `15` |
| Chaos Root chance | `CHAOS_ROOT_CHANCE` | `0.01` (1%) |
| Element/intent metadata (names, bonuses) | `ELEMENT_META` / `INTENT_META` | tables |

## 13. Alchemy — `core/alchemy.py`

| What it does | Constant | Current |
|---|---|---|
| Grade ranking (Mortal → God) | `GRADE_RANK` | table |
| Cauldron quality bonuses | `CAULDRON_BONUS` | table |
| Success/miracle/explosion odds | functions in this file | see code |
| Recipes & pill effects | `migrations/005_alchemy.sql` seed | DB data |

## 14. Auction House — `core/auction.py`

| What it does | Function / default | Current |
|---|---|---|
| Listing fee | `calculate_listing_fee(price, fee_percent)` | `5%` |
| Sale tax (seller proceeds) | `calculate_sale_proceeds(price, tax_percent)` | `5%` |
| Bid increment floor | `validate_bid(..., min_increment_percent)` | `10%` |

> These take a **percentage argument with a default** — if you want to change
> them, pass a flat new value at the call site or change the default. Prefer
> flat stones in new code (the user dislikes %-wise stats).

## 15. Items — `core/items.py` + DB seeds

| What it does | Where | Notes |
|---|---|---|
| Equipment slots & grades | `EQUIP_SLOTS` / `ITEM_GRADES` | `core/items.py` |
| Item templates (pills, talismans, effects) | `migrations/004_items_seed.sql`, `015_stored_qi.sql` | DB data |
| Item effect display text | `format_effect_description()` | `core/items.py` |

## 16. Server timing & economy — `config/default.py`

| What it does | Constant | Current |
|---|---|---|
| `/cultivate` cooldown | `CULTIVATE_COOLDOWN_SECONDS` | `1800` (30 min) |
| Countable messages per hour | `MESSAGE_QI_HOURLY_CAP` | `15` |
| Minimum message length | `MESSAGE_MIN_LENGTH` | `5` |
| Repeat-message window | `MESSAGE_REPEAT_WINDOW_SECONDS` | `60` |
| Groq free-tier rails | `GROQ_*` | model, 5s timeout, 10/hr, 100/day |
| Backup retention | `GITHUB_BACKUP_KEEP` | `14` days |

---

## Cheat-sheet: "I want to change…"

- **A realm's HP** → `core/combat.py` → `HP_MAX`
- **How fast Stored Qi refills** → `core/math.py` → `STORE_QI_BASE_REGEN`
- **How expensive breakthroughs are** → `core/math.py` → `DIFFICULTY`
- **The world boss's damage** → `core/world_events.py` → `BOSS_PHASE_POWER`
- **How long the sect array cooldown is** → `core/sects.py` → `ARRAY_BURST_COOLDOWN`
- **Duel loss Heart Demon** → `core/combat.py`/`cogs/combat.py` — `0.05` (+1 Point) at the duel-loss write
- **Passive chat Qi rates** → `config/default.py` + `core/passive_logic.py`

After editing: **restart the bot** (`Ctrl+C`, then `python run.py`) and run the
test suite once (`python -m pytest -q`) to make sure nothing broke.
