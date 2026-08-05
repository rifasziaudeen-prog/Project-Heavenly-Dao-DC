-- Migration 019 (v1.10.0): Sect array burst — Part 5 · Commit 2.
--
-- The Patriarch can spend flat treasury stones to make the sect array burst,
-- pulsing Stored Qi to every member. `last_burst_at` (ISO-8601 UTC) drives the
-- 6-hour cooldown so the pulse stays special. Pure additive column; the burst
-- math lives in core/sects.py.
ALTER TABLE sects ADD COLUMN last_burst_at TEXT;
