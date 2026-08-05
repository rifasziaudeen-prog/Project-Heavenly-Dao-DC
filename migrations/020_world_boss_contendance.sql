-- Migration 020 (v1.11.0): World-boss Contendance — Part 5 · Commit 3.
--
-- /event_attack is refactored from donation-damage into scripted boss intent
-- patterns fought with the Contendance combat engine. Each participant now
-- carries their own field-battle state:
--   * hp_current   — battlefield HP (realm-based, recovers flat over time)
--   * last_attack_at — drives HP regen and the 30-minute defeat cooldown
--   * boss_round   — this attacker's round index into the boss intent pattern
-- All new columns are nullable/zero-safe for existing participant rows.
ALTER TABLE world_event_participants ADD COLUMN hp_current INTEGER;
ALTER TABLE world_event_participants ADD COLUMN last_attack_at TEXT;
ALTER TABLE world_event_participants ADD COLUMN boss_round INTEGER NOT NULL DEFAULT 0;
