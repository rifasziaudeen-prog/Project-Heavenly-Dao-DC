"""Central configuration.

All environment-driven settings are loaded here from the project root `.env`
file (see `.env.example`). Game-balance constants live in `core/math.py`.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _as_int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _as_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


# --- Discord ----------------------------------------------------------------
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DEV_GUILD_ID: int | None = _as_int(os.getenv("DEV_GUILD_ID"))

# --- Storage ----------------------------------------------------------------
DATABASE_PATH: Path = _as_path(os.getenv("DATABASE_PATH", "heavenly_dao.db"))
MIGRATIONS_DIR: Path = BASE_DIR / "migrations"
TEMPLATES_DIR: Path = BASE_DIR / "templates"
BACKUP_DIR: Path = _as_path(os.getenv("BACKUP_DIR", "backups"))

# --- Off-server GitHub backup mirror (best-effort; see scripts/github_backup.py) ---
GITHUB_BACKUP_TOKEN: str = os.getenv("GITHUB_BACKUP_TOKEN", "")
GITHUB_BACKUP_REPO: str = os.getenv("GITHUB_BACKUP_REPO", "")  # "owner/repo" — use a PRIVATE repo
GITHUB_BACKUP_BRANCH: str = os.getenv("GITHUB_BACKUP_BRANCH", "db-backups")
GITHUB_BACKUP_KEEP: int = _as_int(os.getenv("GITHUB_BACKUP_KEEP")) or 14

# --- Groq free tier (disabled by default; $0 budget) ------------------------
ENABLE_GROQ: bool = os.getenv("ENABLE_GROQ", "false").strip().lower() == "true"
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = "llama-3.1-8b-instant"          # fastest on the free tier
GROQ_MAX_TOKENS: int = 512
GROQ_TEMPERATURE: float = 0.8
GROQ_TIMEOUT_SECONDS: float = 5.0                 # fail fast -> template fallback
GROQ_PLAYER_COOLDOWN_HOURS: int = 24              # max 1 live call / player / 24h
GROQ_GLOBAL_HOURLY_LIMIT: int = 10                # safety rail on free-tier quota
GROQ_GLOBAL_DAILY_LIMIT: int = 100

# --- Gameplay tuning (Phase 1) ----------------------------------------------
CULTIVATE_COOLDOWN_SECONDS: int = 1800            # /cultivate every 30 min
MESSAGE_QI_HOURLY_CAP: int = 15                   # counted messages / player / hour
MESSAGE_MIN_LENGTH: int = 5                       # ignore <5 char messages
MESSAGE_REPEAT_WINDOW_SECONDS: int = 60           # ignore identical repeat within 60s
QI_BUFFER_FLUSH_SECONDS: int = 60                 # memory buffer -> DB flush cadence
QI_BUFFER_MAX_ROWS: int = 4000                    # flush early if buffer explodes
BACKUP_INTERVAL_HOURS: int = 24
PRESENCE_UPDATE_MINUTES: int = 5
WORLD_EVENT_POLL_SECONDS: int = 30                # scheduler cadence
MARKET_EXPIRY_POLL_SECONDS: int = 60              # auction expiry sweep cadence
FLAG_DENY_THRESHOLD: int = 3                      # deny attempts before anti-cheat flag
