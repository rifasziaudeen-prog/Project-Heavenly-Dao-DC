"""Anti-cheat: record suspicious activity for Heaven Panel review."""
from __future__ import annotations

from db.database import Database


async def flag(db: Database, guild_id: int, user_id: int,
               flag_type: str, reason: str, severity: int = 1) -> None:
    await db.execute(
        "INSERT INTO anti_cheat_flags (guild_id, user_id, flag_type, severity, reason)"
        " VALUES (?,?,?,?,?)",
        (guild_id, user_id, flag_type, severity, reason),
    )


async def unresolved_count(db: Database, guild_id: int) -> int:
    row = await db.fetchone(
        "SELECT COUNT(*) AS c FROM anti_cheat_flags"
        " WHERE guild_id=? AND resolved=0",
        (guild_id,),
    )
    return int(row["c"]) if row else 0


async def recent_flags(db: Database, guild_id: int, limit: int = 8) -> list:
    return await db.fetchall(
        "SELECT * FROM anti_cheat_flags WHERE guild_id=? AND resolved=0"
        " ORDER BY id DESC LIMIT ?",
        (guild_id, limit),
    )
