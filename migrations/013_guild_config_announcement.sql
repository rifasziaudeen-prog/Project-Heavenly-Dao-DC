-- 013: guild_config.announcement_channel_id
--
-- The server-setup flow (/setup_server, !setup, scripts/setup_discord_server.py)
-- persists the announcements channel id here — but the column only ever existed
-- in the PostgreSQL schema (011). Without it, the SQLite setup DB write failed
-- with "no such column". Idempotent: the migration runner tolerates a re-run
-- once the column already exists.
ALTER TABLE guild_config ADD COLUMN announcement_channel_id INTEGER;
