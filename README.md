# ☯ Heavenly Dao Engine · 天道引擎

A Xianxia Discord RPG where chat activity becomes cultivation power. Deterministic
mechanics (Qi, realms, tribulations) are 100% hardcoded for balance; narrative
flavor is driven by a zero-cost template engine, with an optional Groq free-tier
LLM plug-in that is **disabled by default**.

**Phase 3 scope (current):** foundation, core loop, P2P Dao Bonds, player-run Sects, spirit stone economy, and the **Inventory & Items System**.

---

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Windows: copy .env.example .env   |   macOS/Linux: cp .env.example .env
python run.py
```

Then open `.env` and paste your bot token (the annotated template in
`.env.example` walks you through every option).

Requirements: Python 3.11+ · a bot token with the **MESSAGE CONTENT INTENT**
enabled (required for passive Qi) — see `.env.example` for the full walkthrough.

## Commands

| Command | Description |
|---|---|
| `/help [category]` | Browse commands by category (Core, Aptitudes, Items, Alchemy, Realms, Events, Laws, Market, Sects & Bonds) |
| `/register` | Awaken your cultivation profile and claim your starter kit (100 💎, Wooden Sword, 3× Qi Gathering Pill) |
| `/cultivate` | Absorb 灵力 (Qi) into your dantian — cooldown shortens as you ascend (~16 min at Mortal, 30 max) |
| `/daily` | Claim a flat spirit-stone tribute every 20 hours (streak milestones at 7/14/30/60/100 days) |
| `/breakthrough` | Attempt a tribulation when your dantian is full (awards spirit stones & item drops on success) |
| `/transcend` | At the summit (Beyond Dao, 9th layer): shed your vessel and restart with permanent gifts |
| `/allocate <stat> [amount]` | Spend stat points earned from breakthroughs |
| `/profile [member]` | View cultivation profile, spirit stone balance, and bond count |
| `/aptitudes [member]` | View Spiritual Root profile — Five Phases, Martial Intents & Yin-Yang balance |
| `/leaderboard` | Top 10 cultivators active in this server (profiles are global — see v1.8.0) |
| `/inventory [page]` | View items in your spatial ring (pills, weapons, scrolls, talismans, materials) |
| `/equip <item_name>` | Equip or unequip weapons or technique scrolls (max 1 weapon, 1 scroll) |
| `/use <item_name>` | Consume pills, talismans, or charms (restores Qi, purges Heart Demon, or grants protection) |
| `/give @user <item_name> [quantity]` | Transfer items to another cultivator in the server |
| `/recharge_artifact [energy]` | Convert spirit stones into spirit energy for your equipped weapon's active ability |
| `/item_info <item_name>` | Inspect grade, lore, item type, equipped status, and parsed effect breakdown |
| `/recipes [grade]` | View known pill recipes, required ingredients, base success rates, and outputs |
| `/alchemy_status` | View your alchemy mastery level, equipped cauldron bonus, fame, and history |
| `/refine_pill <recipe_name>` | Start the 3-stage interactive pill refinement mini-game |
| `/reincarnate` | Voluntarily shed your mortal vessel to be reborn with legacy bonuses (Tier 5+) |
| `/past_lives` | View past reincarnation logs, epitaphs, retained techniques, and past-life memories |
| `/legacy` | Preview stats, bonuses, techniques, and physique retained if reincarnated now |
| `/realms` | View available secret realm dungeons, entry costs, and potential drops |
| `/enter_realm <realm_name>` | Open portal and enter a secret realm dungeon instance |
| `/explore` | Explore the next encounter node in your active secret realm instance |
| `/retreat` | Safely retreat from your active secret realm instance keeping acquired loot |
| `/events` | View active and scheduled World Boss events and calamities |
| `/event_join <event_id>` | Register participation in an active World Event |
| `/event_attack <event_id> <choice>` | Fight the World Boss: pick an intent (Technique / Unfold Law / Artifact / Pill / Retreat) to counter its scripted stance — costs Stored Qi |
| `/event_status <event_id>` | Check World Boss HP bar, current phase, narrative state, and damage leaderboard |
| `/event_claim <event_id>` | Claim post-event loot rewards based on damage rank |
| `/spawn_event <type>` | **Admin.** Schedule or immediately spawn a server World Event |
| `/laws` | View fundamental Dao Laws, your 5-rank mastery, resistance, and next-rank progress |
| `/comprehend <law_name>` | Meditate on a law to gain insight (deterministic, scales with 悟性) (Tier 5+) |
| `/law_status <law_name>` | View detailed lore, the rank ladder, and per-rank effects for a law |
| `/contend @user` | Challenge a cultivator to a Contendance duel (wager spirit stones or fight for honor) |
| `/battle` | Challenge a realm spirit beast to a scripted PvE battle |
| `/learn <technique_name>` | Learn a technique by consuming a Technique Scroll |
| `/techniques` | View your learned techniques, ranks, and rolled entries |
| `/reroll <technique_name>` | Reroll a technique's entries (1 Comprehension Sand + 100 💎) |
| `/market` | Browse active market listings in the Heavenly Auction House |
| `/sell <item_name> <price>` | List an item on the market (5% listing fee, max 5 listings) |
| `/buy <listing_id>` | Instant buy an item at buyout/listed price |
| `/bid <listing_id> <amount>` | Place a bid on an active auction listing (min +10% increment) |
| `/my_listings` | View your active market listings and top bids |
| `/cancel_listing <listing_id>` | Cancel an active listing and return item to inventory |
| `/trade @user <item_name>` | Propose a direct P2P item trade to another cultivator |
| `/trade_accept` / `/trade_decline` | Accept or decline a pending P2P trade offer |
| `/heaven_panel` | **Admin.** Server stats + Dao Punish / Dao Bless / Spawn Event / Broadcast |
| `/dao_config` | **Admin.** Per-guild config (language mode [English/Bilingual], admin role, erasure toggle, channels, gender roles) |
| `/setup_server` | **Admin.** Build the full realm: 34 roles with permissions, 8 categories & 34 channels (incl. voice + hidden staff area), welcome guides, and the self-serve reaction-role board |
| `/dao_bond @user <type>` | Propose a Dao Bond with another cultivator (requires Tier 2+) |
| `/dao_bond_accept @user` / `/dao_bond_decline @user` | Answer a pending bond proposal |
| `/dao_bond_sever @user [reason]` | Sever a bond — public drama, Heart Demon for both |
| `/dao_bonds` | List your active bonds |
| `/dual_cultivate @user` | Cultivate together (bond tier 3+, both must consent) |
| `/sect_create <name>` | Found a new sect (requires Foundation Establishment / Tier 3+) |
| `/sect_join <name>` | Join an existing sect as an Outer Disciple |
| `/sect_leave` | Leave your current sect (Patriarch departure disbands the sect) |
| `/sect_info [name]` | View sect dashboard (members, array level, treasury, roster) |
| `/sect_donate <amount>` | Donate spirit stones to the sect treasury |
| `/sect_upgrade_array` | **Patriarch.** Upgrade the defensive array using treasury funds |
| `/sect_array_burst` | **Patriarch.** Trigger the array — flat treasury cost, pulses +Stored Qi to every member (6h cooldown) |
| `/sect_promote @user` | **Patriarch.** Promote a member one rank step |
| `/sect_demote @user` | **Patriarch.** Demote a member one rank step |
| `/sect_expel @user` | **Patriarch.** Expel a lower-ranked member from the sect |

Passive Qi: every countable chat message awards ~15% of a `/cultivate`. Cap of
**25 messages/hour/player**; messages under 5 chars, duplicates within 60s, and
messages in disabled (spam) channels don't count.

## Newbie Foundations · 入门根基 (v1.14.0)

The two ground layers that make the game actually *playable* from day one:

* **Qi that moves** — `BASE_QI` was front-loaded so filling your dantian is a
  **~10-cultivation goal at every realm** (was ~100 at Mortal: 10 Qi per use
  against a 1,000-Qi dantian — ~50 hours to a first breakthrough). Passive
  chat Qi rose to 15% of a `/cultivate` with a 25-message/hour cap, and the
  `/cultivate` cooldown now scales with realm (~16 min at Mortal → 30 min
  cap), so the early game stays snappy. A new cultivator can reach their
  first breakthrough in a single evening session.
* **An economy that seeds** — `/register` now grants a starter kit
  (**100 💎** + a Wooden Sword + 3× Qi Gathering Pills), `/daily` pays a flat
  per-realm spirit-stone tribute every 20 hours with **flat streak
  milestones** (no percentages anywhere), and each successful breakthrough
  now pays **+25 💎** (was +10).
* **The register trap fixed** — a new player who chats *before* running
  `/register` (passive Qi auto-creates the account) used to be told
  "Already Awakened" forever, with no aptitudes, no Stored Qi pool, and no
  starter kit. `/register` now detects the unawakened row and runs the full
  awakening.
* All numbers live as named constants in `core/math.py` / `core/items.py`
  (`BASE_QI`, `DAILY_STONES`, `DAILY_STREAK_MILESTONES`, `STARTER_KIT`, …) —
  see `BALANCE.md`.

## Game design (per the v2.0 blueprint + Kimi review)

* **Balance**: exponential breakthrough difficulty (15 → 167,000) across a
  16-realm × 9-layer ladder, Heart Demon non-linear penalty, Karma ±10%, sect
  bonus, and a **Dao Mercy** pity system (+5% per failed attempt, capped
  +25%). Success chance is clamped to 5–95%.
* **Qi economy**: diminishing returns on comprehension (logarithmic), companion
  bonuses additive & hard-capped at 2x, array bonus capped at +50%.
* **Heavenly Dao Erasure**: 0.5% on tier 8+ **failures**. Without a charm you
  fall to Mortal but keep 25% 悟性 (comprehension) and 10% 气运 (luck) plus the
  **Ashen Remnant** title — never account death. Charms (found on 5% of
  successful breakthroughs, or granted by the Heaven) change the outcome.
* **Zero LLM cost**: all narrative comes from weighted templates in SQLite.
  The Groq client (`ENABLE_GROQ=true`) is wired for Tier-4 moments with strict
  rate limits (1/player/24h, 10/hour global) and automatic template fallback.
* **Language Modes**: Server admins can toggle between **Pure English UI** (`/dao_config language:english`) and **Bilingual UI** (`/dao_config language:bilingual`).

## 16 Realms × 9 Layers + Transcendence (v1.4.0)

The cultivation ladder spans **16 realms × 9 layers** (144 sub-stages). The
first nine realms follow the classic Xianxia path; the top seven ascend
beyond the mortal heavens:

| # | Realm | # | Realm |
|---|---|---|---|
| 1 | Mortal 凡人 | 9 | Tribulation Transcendence 渡劫 |
| 2 | Qi Condensation 炼气 | 10 | True Immortal 真仙 |
| 3 | Foundation Establishment 筑基 | 11 | Golden Immortal 金仙 |
| 4 | Core Formation 金丹 | 12 | Primordial Chaos 混沌 |
| 5 | Nascent Soul 元婴 | 13 | Dao Ancestor 道祖 |
| 6 | Soul Transformation 化神 | 14 | Heavenly Venerable 天尊 |
| 7 | Void Refinement 炼虚 | 15 | Great Emperor 大帝 |
| 8 | Dao Fusion 合体 | 16 | Beyond Dao 超脱 |

* Each realm has **9 layers** (一层 → 九层); the 9th layer is the tribulation
  gate. Breakthrough difficulty is exponential and all existing mechanics
  (Dao Mercy, Heart Demon, Heavenly Dao Erasure at tier 8+) apply at realm
  boundaries.
* **Transcendence** (`/transcend`) unlocks at **Beyond Dao (16th realm, 9th
  layer)** — a voluntary prestige loop, separate from Reincarnation. It resets
  your realm, Qi, and Heart Demon but permanently stacks: **+15 to all five
  core stats**, **+5,000 Qi capacity** (survives every future breakthrough),
  **+100 flat Qi per `/cultivate`**, an exclusive **Transcendent I/II/III…**
  title, and one cycling permanent passive per cycle (Boundless Dantian,
  Immortal Vessel, Unyielding Dao Heart, Celestial Fortune, Ancient Soul,
  Transcendent Physique). Your items, sect, bonds, karma, aptitudes, and Dao
  Laws all survive the reset.

## Stored Qi · 存灵气 (v1.5.0)

**Stored Qi** is the all-rounder resource pool — separate from your dantian Qi.
It will power techniques, artifacts, and law-folding in combat, and can also be
spent by future systems. Think of it as your *reserve of intent*.

* **Randomized awakening max**: every cultivator rolls **100–300 Stored Qi**
  on `/register`; a **Chaos Five-Element Root (混沌五行根)** grants **+50**.
  Future systems (e.g. Heaven-Chosen physiques, passives) stack flat bonuses on
  top via `stored_qi_max_bonus`.
* **Slow natural regen**: **4 Stored Qi per hour** (about a day for a full
  pool) — deliberate pacing. Regen can be sped with pills, passives, and
  techniques via a flat, capped regen bonus (+20/h max). The bot ticks this
  hourly.
* **Pills**: `Stored Qi Elixir` (+30), `Stored Qi Concentrate` (+80), and
  `Stored Qi Heavenly Dew` (+200) restore the pool instantly via `/use`.
* **Burn to continue (overdraft)**: when Stored Qi runs dry mid-fight, you may
  **burn your cultivation base** — dantian Qi is consumed permanently at a
  fixed per-realm cost (no percentages; one flat table in `core/math.py`).
  Consequences escalate by burn count: **3rd** → Heart Demon +2 Points, **5th** →
  forced retreat or Qi Deviation (failure drops one layer), **7th** → Heavenly
  Dao Erasure check (tier 8+). The interactive burn button arrives with the
  combat engine; the deterministic rules are already in and tested.
* Your current pool and regen rate appear in `/profile` under **Stored Qi · 存灵气**.

## Spiritual Aptitudes & Martial Intent Engine (v1.1.0)

Every cultivator awakens with a unique Spiritual Root (灵根) — a randomized profile of **Five Phases aptitudes (五行)**, **Martial Weapon Intents (武道真意)**, and a **Yin-Yang balance (阴阳)** that shapes how they grow and fight.

* **Awakening Roll** (assigned automatically on `/register`):
  * **60-point pool** distributed randomly across the 6 elemental aptitudes, with no single element above **25**.
  * **30-point pool** across the 4 martial intents, no single intent above **15**.
  * **1% Chaos Five-Element Root (混沌五行根)**: a legendary balanced roll setting *all* elements to 20–25 — equally attuned to every phase, compatible with all manuals.
  * Yin-Yang balance starts at **0 (Balanced)**; `special_root` is NULL unless a Chaos Root was rolled.
* **Five Phases (五行)** — Fire 🔥 · Water 💧 · Wood 🪵 · Metal 🪙 · Earth 🪨 · Qi ✨. Each aptitude (0–100) grants a scaling stat multiplier `(aptitude / 100) × max_bonus`:
  * **Fire** — up to +20% crit chance, +50% crit multiplier.
  * **Water** — up to +15% evasion, +10% speed, +10% vitality recovery.
  * **Wood** — up to +20% toxin/debuff immunity.
  * **Metal** — up to +25% armor penetration, +15% raw damage.
  * **Earth** — up to +20% CC resistance, +15% barrier shielding.
  * **Qi** — up to +30% Qi regen speed, +20% Qi gain (wired into `calculate_qi_gain`), +15% dantian efficiency.
* **Martial Weapon Intents (武道真意)** — Sword 🗡️ · Sabre 🪓 · Spear 🔱 · Fist 👊:
  * **Sword Intent** — up to +15% multi-hit trigger chance.
  * **Sabre Intent** — up to +20% cleave damage, +10% lifesteal.
  * **Spear Intent** — up to +15% counter-attack, +12% armor break chance.
  * **Fist Intent** — up to +25% armor-ignoring dantian Qi damage.
* **Yin-Yang Balance (阴阳)** — ranges −100 (Pure Yin) to +100 (Pure Yang):
  * **Yang** (+): physical fortitude and external power — up to +10% Yang fortitude.
  * **Yin** (−): phantom evasion and heart-demon resistance — up to +10% Yin Heart Demon resistance.
  * The `/aptitudes` embed colour-codes by alignment: gold (Pure Yang), cyan (balanced), violet (Pure Yin).
* **Equipment Prerequisites**: high-tier weapons and technique scrolls may embed aptitude requirements in their effect data (keys like `min_affinity_fire` or `min_intent_sword`) — `core/items.py` refuses to equip them until the cultivator's profile qualifies.
* **Commands**: `/aptitudes [member]` — full Spiritual Root profile with progress bars, dominant element & intent, Yin-Yang gauge, and any special root.
* **Growth sources**: aptitudes rise through secret realm epiphanies, alchemy elixirs, Dao Law comprehension, and World Boss victories. The `special_root` column is designed to be extended (future roots like `heavenly_fire`, `yin_phantom`); Artifact Spirits (器灵) are deferred to a later migration.

## Dao Bonds — companions are real people (review v2)

Dao Companions, sworn siblings, masters & disciples, rivals, and dual
cultivation partners are **bonds between actual server members**, not NPCs.

* **Bond types**: 道侣 Dao Companion · 义兄姊 Sworn Sibling · 师徒 Master-Disciple
  · 宿敌 Rival · 同门 Sect Sibling · 双修伴侣 Dual Cultivation Partner
* **Minimum realm gate**: Mortals (tier 1) cannot form bonds; both players must
  be **Qi Condensation (炼气, tier 2)** or higher.
* **Gender rules** (admin-set via `/dao_config` → `dao_male_role` /
  `dao_female_role`): both players must hold a mapped role, and **same-gender
  pairs cannot form romantic bonds** (no marrying one's own gender).
* **Fickle Heart stigma**: severing a romantic bond and proposing a new one
  within 7 days brands the player **薄情寡义 Fickle Heart** on `/profile`.
* **Realm gaps**: romantic bonds within 1 realm; other bonds up to 3; a master
  must be 2+ realms above the disciple.
* **Polygamy limits**: 3 Dao Companions · 1 Dual Cultivation Partner · 5 Sworn
  Siblings · 3 Disciples (1 master each) · 1 Rival · 10 Sect Siblings.
* **Synergy** is computed from real stats: complementary stats, shared karma
  path (×1.2 vs ×0.7), realm proximity, and bond tier.
* **Severance drama**: both gain Heart Demon (tier × 1 Point); the severer loses
  100 karma; the victim gains the **Betrayed** title and a +15% breakthrough
  buff for 7 days (rage cultivation).
* **Dual cultivation** (`/dual_cultivate`) requires a Dao Companion or Dual
  Cultivation Partner bond at tier 3+, a 4h cooldown, and **both players must
  press Consent** — a real-time two-player ritual.

## Sects & Spirit Stones Economy (Phase 2)

Cultivators can form and manage player-run organizations with rank hierarchies,
treasuries, and defensive array upgrades.

* **Creation gate**: requires **Foundation Establishment (筑基, tier 3+)**; sect
  name must be 2–40 characters.
* **Five-rank hierarchy**: Outer Disciple (外门弟子) → Inner Disciple (内门弟子) →
  Core Disciple (亲传弟子) → Elder (长老) → Patriarch (宗主).
* **Rank permissions**: Patriarchs can promote, demote, expel members, and
  upgrade the sect's defensive array.
* **Array upgrade economy**: array levels (1–7) provide breakthrough success
  bonuses (up to +56%). Upgrades are funded from the sect treasury with exponential
  cost `int(500 × 1.5^(level-1))`.
* **Array burst (v1.10.0)**: the Patriarch can spend **flat treasury stones** to
  make the array burst — every member instantly gains Stored Qi. Level 1:
  **500 💎 → +30 Stored Qi** per member; each array level past 1 adds +250 💎
  cost and +10 Stored Qi pulse. Cooldown **6 hours** (tracked by `last_burst_at`,
  visible on `/sect_info`). No percentages — one plain table in `core/sects.py`.
* **Spirit stone wallet**: players earn **+25 spirit stones** per successful
  breakthrough (v1.14.0), plus the `/daily` tribute and `/register` starter
  kit. Stones can be donated to the sect treasury via `/sect_donate`.

## Artifact Active Abilities · 法宝 (v1.13.0)

Equipped weapons can carry a **spirit-energy active ability** — a charged
strike you unleash by choosing the Artifact intent in combat.

* **Actives live on the item** — a weapon's `effect_data` may carry
  `"active_ability": {"name", "power", "energy_cost"}` (seeded on the
  **Heavenly Flame Blade** and the new God-grade **Sword of Annihilation**).
* **Spirit energy pool** — each active has an energy cap (default 100) that
  depletes on activation. Energy recharges **flat over time** (10/hour) or
  instantly via **`/recharge_artifact`** (1 💎 per energy point).
* **In combat** — choosing 🗡️ Artifact with a charged active strikes with its
  power **and** keeps the parry; when it's recharging, the intent is a pure
  guard. Works in `/contend`, `/battle`, and the World Boss.
* Tuning lives in `core/items.py` (`ARTIFACT_ENERGY_MAX`,
  `ARTIFACT_ACTIVE_COST`, `ARTIFACT_RECHARGE_PER_HOUR`, …) — see `BALANCE.md`.

## Inventory & Items System (Phase 3, Step 1)

Cultivators collect, equip, consume, and trade items across five grades (`Mortal`, `Earth`, `Heaven`, `Immortal`, `God`).

* **Item Types**:
  * **Pills**: Consumables for instant Qi restoration (`qi_boost`) or Heart Demon purging (`heart_demon_purge`).
  * **Weapons**: Equipable gear providing passive stat boosts (`stat_buff` for Physique, Spirit, Luck, Comprehension).
  * **Technique Scrolls**: Equipable scriptures granting passive breakthrough success rate bonuses (`breakthrough_aid`).
  * **Talismans**: Protective artifacts that grant Heavenly Dao Erasure protection charms (`karmic_shield`, `reincarnation_seed`, `dao_heart_anchor`).
  * **Materials**: Ingredients reserved for alchemy and crafting.
* **Equipment Constraints**: Maximum **1 Weapon** and **1 Technique Scroll** equipped simultaneously.
* **Drop Sources**: Breakthrough success (Charms 5%, Pills 15%, Scrolls 8%), Cultivate streaks (Materials 20%, Talismans 10%), and Sect array weekly distributions.

## Alchemy Mini-Game (Phase 3, Step 2)

Cultivators combine gathered materials into potent elixirs through a 3-stage interactive mini-game.

* **Mini-Game Stages**:
  * **Stage 1 (Fire Control)**: Button rhythm game repeating a shown flame pattern (`Low`, `Medium`, `High`).
  * **Stage 2 (Ingredient Sequence)**: Interactive Select Menu choosing the correct ingredient addition sequence.
  * **Stage 3 (Spiritual Sense)**: Comprehension stat check against recipe difficulty.
* **Refinement Outcomes**:
  * 🎉 **Success**: Refines target pill and adds it to spatial ring.
  * ✨ **Miracle (1% Chance)**: Celestial aura upgrades the output with a **1.5x effect multiplier**.
  * 🌫️ **Failure**: Materials lost to dross + 0.2 Heart Demon Points.
  * 💥 **Explosion**: Violent flame eruption costs **25% Qi** + **1 Heart Demon Point**.
## Reincarnation System — "Death Is Not The End" (Phase 3, Step 3)

Cultivators can voluntarily shed their mortal shell (Tier 5+ with half-full dantian) or undergo forced rebirth upon Heavenly Dao Erasure at Tier 8+.

* **Legacy Retention**: Retains **25% Comprehension**, **10% Luck**, **50% unspent stat points**, and **1 inherited technique scroll** carried over into the next lifetime.
* **Cycle Advantages**: Stacking **+5% breakthrough success rate bonus per cycle** (max +25%) and unique reincarnated physiques (`Mortal Meridian` → `Reincarnated Soul` → `Twice-Born Dao Heart` → ... → `Heavenly Dao Reject`).
* **Epitaphs & Memory Unlocks**: Automatically generates past life epitaphs via template engine and unlocks past life memories as Comprehension reaches 100, 250, 500, and 1000 thresholds.

## Secret Realms Dungeon System (Phase 3, Step 4 & Step 5)

Cultivators venture into ancient secret realm instances to battle beasts, disarm formations, and claim rare celestial loot.

* **Branching Node Encounters**: `Monster` (Physique/Spirit combat check), `Treasure` (ancient chest opening), `Trap` (Luck disarm check), and `Herb_Garden` (Comprehension harvesting).
* **Final Depth Bosses**: Final dungeon node spawns a Guardian Boss with scaled difficulty.
* **Safe Retreat**: Players can `/retreat` at any node to escape safely with all accumulated loot.
* **Groq Tier-4 Integration**: Optional Groq LLM client (`core/groq_client.py`) generates rich narrative flavor with seamless fallback to `TemplateEngine`.

## World Events & Heavenly Calamities (Phase 4, Step 1) — World-boss Contendance (v1.11.0)

Server-wide World Boss encounters scheduled in advance featuring 5 event types and 5 boss HP phases — now fought with the **Contendance combat engine** instead of donation-damage.

* **5 Event Types**: Demon Beast Siege, Heavenly Tribulation Rain, Ancient Ruin Awakening, Sect War, and Dao Competition.
* **5 Boss HP Phases**: `Normal` (100%→75%) → `Enraged` (75%→50%) → `Minions Spawned` (50%→25%) → `Desperation` (25%→10%) → `Final Stand` (10%→0%). Each phase is a **flat power table** (`18 → 24 → 30 → 38 → 48`).
* **Scripted intent patterns**: each event type cycles a scripted boss stance — `gathers Sword Intent to unleash` (unfold), `rears back for a devastating strike` (technique), or `regroups` (pass). `/event_attack` shows the stance; you counter it.
* **Counter-play with laws**: on an unfold round, unfolding **Law of Sword two ranks ahead** (rank 2+) of the boss's grasp is a **deterministic counter** — full damage to the boss, no damage to you. Technique rounds are parried by artifacts and blunted by law guards.
* **Stored Qi per round**: every attack spends Stored Qi (technique cost, unfold 30, artifact 10); the pill intent restores Stored Qi from inventory. Your **battlefield HP** persists across attacks, recovers flat over time, and being overwhelmed is **no death** — just **+1 Heart Demon Point** and a 30-minute recovery window.
* **Combat damage → boss bar**: the engine's round damage is flat-scaled (`BOSS_DAMAGE_SCALE = 30`) onto the colossal boss HP bar — one named constant.
* **Leaderboard Rewards**: Top damage ranks earn unique titles, God/Immortal/Heaven-grade loot items, and spirit stone rewards.

## Dao Laws Endgame System — 5 Ranks (v1.6.0)

High-tier cultivators (Nascent Soul / Tier 5+) comprehend the 5 Fundamental Laws of Existence (`Space`, `Time`, `Karma`, `Sword`, `Alchemy`). Each law has **5 Ranks**, unlocking at 20/40/60/80/100 mastery:

* **Rank ladder** — Rank 1 **Insight 洞察** · Rank 2 **Comprehension 领悟** · Rank 3 **Realization 真悟** · Rank 4 **Enlightenment 明悟** · Rank 5 **Transcendence 超脱**.
* **Resistance (5% → 25%)** — every rank grants **5% damage reduction** against attacks of that law's type (Rank 5 = 25%). Two ranks ahead of an attacker means a **deterministic counter** — no dice, no percentages-of-percentages.
* **Aptitude = learning speed** — insight gain is deterministic: **`2 + 悟性 ÷ 100`** mastery points per `/comprehend`, with flat bonuses from other sources (secret realms +4, tribulations +8). High-悟性 cultivators climb ranks faster; that's the payoff of the stat.
* **Rank effects** — each rank unlocks the law's effect ladder (`Void Step`, `Temporal Cultivation`, `Sword Intent`, `teleport`, and new Rank-5 capstones like `space_dominion` / `karmic_justice`).
* **Dao Fusion Prerequisites**: reaching **Rank 5 (100% Complete Mastery)** in at least 1 Fundamental Law is required for **Dao Fusion Ascension (Tier 8→9)**.
* **All numbers are named constants in one file** (`core/dao_laws.py`) — tuning a rank threshold or resistance is a one-line change.

## Auction House & P2P Trading (Phase 4, Step 3)

A fully player-driven economy without NPC merchants — list, bid, buyout, and trade items for spirit stones.

* **Market Listings**: `/sell` items for spirit stones with a 5% upfront listing fee (max 5 active listings per player).
* **Bidding & Buyout**: Place bids with a minimum +10% increment over the current bid (bids held in escrow with auto-refund for outbid players) or `/buy` instantly at buyout price.
* **Seller Tools**: `/my_listings` reviews all your active listings with top bids and buyouts; `/cancel_listing <id>` delists one — refunding the 5% listing fee, returning the item to your `/inventory`, and releasing any escrowed bid back to the bidder.
* **Listings Expire**: `/sell` accepts `duration_hours` (1–168, default 24). A background sweep (every 60s) expires due listings: it marks them `expired`, refunds any escrowed bid to the bidder, and returns the item to the seller's inventory. No fee refund on natural expiry.
* **5% Market Sales Tax**: Deducted from seller proceeds upon successful item purchase.
* **Direct P2P Trading**: `/trade @user` offers direct item-to-item transfers with a 10-minute confirmation window.

## Crash-Safe Economy · 铁律账本 (v1.15.0)

Every multi-step money/item flow runs inside **`db.transaction()`** — a single
SQLite transaction that commits all statements as one unit or rolls everything
back on any failure (or a crash — SQLite rolls back open transactions on
process death, which is exactly what a rollback reproduces).

* **Wrapped flows:** `/buy`, `/bid`, `/sell`, `/cancel_listing`, `/trade_accept`,
  reincarnation rebirth, duel settle/refund, battle rewards, `/learn`, `/reroll`,
  intent spending, cultivation-base burns, and sect create/disband/donate/burst.
* **Atomic race guards:** the auction's `WHERE status='active'` + `rowcount`
  claims now run as the FIRST statement inside the transaction and raise on a
  lost race — the claim and the money movement can never be torn apart.
* **Reentrant write lock:** background loops (auction sweep, Stored-Qi regen,
  Qi flush) wait for an open transaction instead of being silently absorbed
  into it and rolled back with it.
* **Nested blocks** use SAVEPOINTs, so an inner failure rolls back only itself.
* Rule of the road: read before the block, no Discord awaits inside it.

## Project layout

```
bot/            Discord bot assembly + background tasks (qi flush, presence,
                daily backup, world-event scheduler)
cogs/           Slash-command modules (alchemy, auction, cultivation, dao_bonds, dao_config, dao_laws,
                heaven_panel, items, passive_qi, reaction_roles, reincarnation, secret_realms, sects, world_events)
core/           Deterministic math, template engine, Groq client, anti-cheat, server layout blueprint,
                alchemy, auction, dao_bonds, dao_laws, items, reincarnation, secret_realms, sects, world_events
db/             Async SQLite & PostgreSQL layers (database.py, postgres.py), migration runner, queries
migrations/     Versioned SQL migrations (001_init to 018_global_players; postgres/011 + 012)
scripts/        Automation scripts (setup_discord_server.py, migrate_sqlite_to_postgres.py,
                validate_migration.py, github_backup.py)
templates/      Narrative fragment JSON — add files to extend flavor
config/         Env-driven settings (default.py, postgres.py)
tests/          pytest suite (277 tests covering balance, bonds, sects, items, alchemy, reincarnation,
                secret realms, world events, dao laws, auction, affinities, combat, global players,
                postgres, migrations, github backup, server layout)
```

## Backups & disaster recovery

* **Daily snapshots** — the bot writes `backups/heavenly_dao_YYYY-MM-DD.db` via
  `db/database.py::backup_database` (idempotent — one per day).
* **Off-server GitHub mirror** — `scripts/github_backup.py` pushes each daily
  snapshot to a dedicated branch in a GitHub repository using the Contents API
  (no git install needed on the host, `aiohttp` only). Configure it in `.env`:
  `GITHUB_BACKUP_TOKEN`, `GITHUB_BACKUP_REPO`, `GITHUB_BACKUP_BRANCH`,
  `GITHUB_BACKUP_KEEP` (see `.env.example`). It runs automatically after every
  daily snapshot, prunes old snapshots, and can be run manually:

  ```bash
  python scripts/github_backup.py
  ```

  > **Security:** the database contains player data — point
  > `GITHUB_BACKUP_REPO` at a **PRIVATE** repo and scope the token to it.
* **Why**: a free hosting provider can purge your server (e.g. wispbyte's
  14-day inactivity rule). Your code lives on GitHub — and now so do your
  player-data snapshots.

## Server blueprint (the v2 realm)

`/setup_server` (and the `!setup` fallback, and `scripts/setup_discord_server.py`)
build the whole server from **one source of truth** — `core/server_layout.py` —
so the slash command, the text fallback, and the standalone script can never
drift apart. Setup is fully idempotent: run it again and it only creates what's
missing.

**What it builds (34 roles · 8 categories · 34 channels):**

* **Roles with real permissions** — 👑 Dao Ancestor (full admin), 🛡️ Heavenly
  Enforcer / ⚖️ Law Keeper / 🧹 Sect Steward (graduated moderation), all 16
  realm tiers, plus self-assignable ☯️ gender, ⚔️ martial-path, 🌱 element-root,
  and 📖 culture roles.
* **Themed categories** — 🌄 Mortal World (welcome, rules, announcements,
  role-selection, status), 📖 Scriptures, 🌌 Cultivation Grounds, 🏯 Sects &
  Bonds, ⚔️ Calamities & Events, 🗣️ Immortal Pavilion (social + 2 voice
  rooms), 📜 Records & Archives, and a hidden 🏛️ Heavenly Court staff area.
* **Channel permission overwrites** — read-only info channels (mortals read,
  staff post), staff-only hidden channels, and per-role allow/deny rules
  declared right in the blueprint.
* **Reaction roles** — the role-selection board lets members claim their
  gender/path/root/culture with a tap; exclusive groups auto-swap (one gender,
  one path, one root). Handled by `cogs/reaction_roles.py`.
* **Welcome experience** — 5 guides auto-posted (welcome, rules & commands,
  getting-started, command reference, role-selection board), pinned where it
  matters, and `guild_config` (admin role + gender mapping + announcement
  channel) written automatically.

To rebuild on a fresh server: invite the bot, run `/setup_server` once, done.

## Testing

```bash
.venv/Scripts/python -m pytest -q
```

## Documentation

* **`README.md`** — this file: setup, commands, design, roadmap
* **`BALANCE.md`** — the tuning sheet: every game number → its exact constant and file
* **`CHANGELOG.md`** — version history (Keep a Changelog format)
* **`MIGRATION.md`** — SQLite → PostgreSQL path and the P0 schema decisions
* **`DEPLOY_WISPBYTE.md`** — free 24/7 hosting walkthrough (wispbyte)
* **`.env.example`** — annotated template for every environment variable

## Developer tooling

Two scripts keep changes cheap and docs honest:

```bash
# Scaffold a new feature: auto-numbers the migration, creates the stub,
# and patches the version assertions that used to break the test suite.
python scripts/new_feature.py <snake_case_name>        # add --dry-run to preview

# Drift-linter: verifies README test count, command table, CHANGELOG
# ordering, and migration version lists against the real code.
python scripts/check_docs.py                            # add --quick to skip pytest
```

Rules of thumb when changing anything:
* Game numbers go in named constants inside `core/*.py` — see `BALANCE.md`.
* New slash commands need a README table row (or `check_docs.py` will fail).
* New migrations go through `new_feature.py` (or patch the version lists by hand).

## Troubleshooting

* **Slash commands don't appear** — commands sync globally by default and can
  take up to an hour. Set `DEV_GUILD_ID` to your server ID in `.env` for
  instant sync.
* **No passive Qi from chat** — enable the **MESSAGE CONTENT INTENT** in the
  Discord Developer Portal (Bot > Privileged Gateway Intents) and restart.
* **`DISCORD_TOKEN is not set`** — you haven't created `.env` from
  `.env.example` yet.
* **Techniques not appearing after learning** — the bot syncs the catalog at
  startup; `/learn` only works after a restart that applied migration 017.
* **Bot hangs on Ctrl+C / can't restart** — fixed in v1.8.1: shutdown now
  closes the SQLite connection (and the aiosqlite worker thread is daemonized),
  so Ctrl+C exits cleanly instead of leaving a zombie process holding
  `heavenly_dao.db` locked. If you still have an old stuck process, kill it
  with `taskkill /F /PID <pid>` (find it via `tasklist | findstr python`).
* **Players report `/register` failing** — usually the same stuck-process DB
  lock (`database is locked`); restart the bot. Register itself is verified
  working.
* **Database keeps growing** — expected: `qi_buffer` is an append-only audit
  log. It gets monthly partitioning in the PostgreSQL migration.

## Global Player Profiles (v1.8.0)

Since migration 018, **players are GLOBAL** — one cultivation life per Discord
user, identical in every server the bot serves. A cultivator who registers in
Server A keeps their realm, Qi, items, techniques, laws, bonds, and
reincarnation lives when they play in Server B.

* **One row per user** — the old `UNIQUE(guild_id, user_id)` per-guild isolation
  is replaced by `UNIQUE(user_id)`. Migration 018 merges any pre-existing
  duplicates keep-the-strongest (highest realm wins) and reparents every
  player-owned row (items, techniques, laws, bonds, companions, reincarnation
  lives, realm runs, market listings, combat history) onto the survivor.
* **The world stays per-server** — guild config, world events, qi audit logs,
  anti-cheat flags, combat logs, and the auction house's server context remain
  per-server; sects and Dao Bonds are global by design.
* **Per-server leaderboards** — each player tracks `last_active_guild_id`;
  `/leaderboard` and the Heaven Panel rank the cultivators who last played in
  *this* server, showing their global progress.
* **Global Groq quotas** — LLM rate limits are per user, not per (user, guild).

## Heart Demon Points · 心魔 (v1.9.0)

The engine stores Heart Demon internally as a **0–1.0 ratio**, but players see
it as a clean **0–20 point scale** — boring percentages are gone from the UI.

* `/profile` shows `Heart Demon · 心魔: X/20`.
* **Duel losses** give a flat **+1 Heart Demon Point** (internally +0.05).
* All Heart Demon messages speak in points: alchemy explosions (+1 Point),
  refinement frustration (+0.2 Points), beast-battle flee (+0.4 Points),
  burn-to-continue (3rd burn +2 Points), Dao Bond severance (tier × 1 Point),
  Heart Demon purge pills (−N Points), and the Heaven Panel's Dao Punish
  (+4 Points) / Dao Bless (clear to 0).
* Mapping lives in `core/math.py`: `heart_demon_points()` and
  `heart_demon_delta_str()` — the engine math never changed, only the display.

## Contendance Combat Engine (v1.7.0)

**Contendance** (论道决斗) is the duel engine — every round resolves from flat
stats, technique power, and law mastery plus one **d20 roll per fighter** (no
hidden multipliers or percentage stacking).

* **Techniques** — a 12-entry catalog (White → Red quality) with Dao-Law
  affinities. Learn them via `/learn` (consumes a Technique Scroll); every new
  cultivator receives a free starting technique at `/register`. Techniques roll
  **1–3 deterministic entries** — Afterimage (+15 negation), Penetration
  (ignores 1 law-resistance rank), Overcharge (double damage / double Stored Qi
  cost), Karmic Weight (+5 per 1,000 enemy karma) — rerollable with
  **Comprehension Sand** via `/reroll`.
* **Duels (`/contend`)** — challenge a cultivator; the target accepts or
  declines (wagers optional). Each round both fighters privately commit an
  intent (⚔️ Technique · ☯️ Unfold Law · 🗡️ Artifact · 💊 Pill · 🏳️ Retreat)
  on a **20-second blind window** — you never see your opponent's pick. The
  Clash resolves: technique power + d20 vs. parry, **5% → 25% law resistance**,
  **2-ranks-ahead deterministic counter**, and a narrative Revelation after
  every round. Duels cap at **30 rounds** — a stall (pill vs pill) ends by
  remaining HP.
* **Dao Heart** — a 100-point mental pool drained by heart-demon intents; at 0
  you are forced to retreat and suffer a Heart Demon spike.
* **Burn Cultivation Base** — sacrifice **dantian Qi** (your cultivation  base, flat per-realm cost) to instantly recover **+100 Stored Qi** and keep
  fighting: 3rd burn +2 Heart Demon Points, 5th forced deviation/retreat, 7th
  an erasure check on Tier 8+ (all within the current fight).
* **Spirit Beasts (`/battle`)** — scripted PvE: beasts telegraph their intent
  for 1–3 phases so you can counter them, exactly like the Ancient Sword Spirit
  gathering Sword Intent.
* First to **0 HP** is defeated (never killed), or the duel ends by retreat /
  Dao Heart break / burn deviation. Combat is logged to `combat_log` for
  future leaderboards.

## Roadmap

* **Phase 1 (foundation):** core loop, passive Qi, admin panel, template engine *(Completed)*
* **Phase 2 (social):** sects, player-to-player Dao Bonds, spirit stone economy *(Completed)*
* **Phase 3 (advanced):** inventory & items *(Completed)*, alchemy mini-game *(Completed)*, reincarnation *(Completed)*, secret realms *(Completed)*, Groq Tier-4 wiring *(Completed)*
* **Phase 4 (world):** world-event mechanics *(Completed)*, Dao Laws endgame *(Completed)*, auction house / P2P trading *(Completed)*, PostgreSQL migration *(Completed)*
* **v1.5.0:** Stored Qi · 存灵气 all-rounder pool *(Completed)*
* **v1.6.0:** Dao Law ranks + aptitude learning speed *(Completed)*
* **v1.7.0:** Contendance combat — techniques, duels, PvE battles, Dao Heart, burn-to-continue *(Completed)*
* **v1.8.0:** Global player profiles *(Completed)* — see the [dedicated section](#global-player-profiles-v180)
* **v1.9.0:** Heart Demon Points — visible 0–20 scale over the internal ratio *(Completed)* — see the [dedicated section](#heart-demon-points--心魔-v190)
* **v1.10.0:** Sect array burst — Patriarch-triggered Stored Qi pulse for the whole sect *(Completed)* — see the [sect section](#sects--spirit-stones-economy-phase-2)
* **v1.11.0:** World-boss Contendance — scripted boss intents, law counters, Stored Qi stakes, battlefield HP *(Completed)* — see the [world events section](#world-events--heavenly-calamities-phase-4-step-1--world-boss-contendance-v1110)
* **v1.12.0:** Developer experience upgrade — `BALANCE.md` tuning sheet, `new_feature.py` scaffolder, `check_docs.py` drift-linter *(Completed)*
* **v1.13.0:** Artifact active abilities — spirit-energy weapon strikes with time/stone recharge *(Completed)* — see the [dedicated section](#artifact-active-abilities--法宝-v1130)
* **v1.14.0:** Newbie Foundations — front-loaded Qi curve, `/daily` tribute, `/register` starter kit, register trap fixed *(Completed)* — see the [dedicated section](#newbie-foundations--入门根基-v1140)
* **v1.15.0:** Crash-Safe Economy — `db.transaction()` atomic write blocks across auction, combat, sects & reincarnation *(Completed)* — see the [dedicated section](#crash-safe-economy--铁律账本-v1150)

---

### 🎉 HEAVENLY DAO ENGINE v1.1.0 — FULL RELEASE COMPLETE!

