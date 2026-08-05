-- Migration 022: Daily claim
--
-- The newbie-economy foundation: every cultivator can claim a flat spirit-
-- stone tribute once per 20 hours (/daily). The per-realm amounts and the
-- streak milestones live as named constants in core/math.py (DAILY_STONES,
-- DAILY_STREAK_MILESTONES) — never magic numbers here.

ALTER TABLE cultivators ADD COLUMN last_daily_at TEXT;
ALTER TABLE cultivators ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0;
