"""Shared data-access helpers used across cogs (keeps SQL in one place)."""
from __future__ import annotations

import sqlite3

from core import math as gm
from db.database import Database


async def get_or_create_cultivator(
    db: Database, guild_id: int, user_id: int, username: str
) -> tuple[dict, bool]:
    """Returns (row_dict, was_created). Per-guild isolation enforced by the unique index.

    A concurrent first interaction (e.g. a message and /register racing) can hit
    the unique index with two INSERTs — the loser is recovered by re-fetching.
    """
    row = await db.fetchone(
        "SELECT * FROM cultivators WHERE guild_id=? AND user_id=?", (guild_id, user_id)
    )
    if row:
        return dict(row), False
    try:
        cursor = await db.execute(
            "INSERT INTO cultivators (user_id, guild_id, username, qi_capacity)"
            " VALUES (?,?,?,?)",
            (user_id, guild_id, username, gm.qi_capacity_for(1)),
        )
    except sqlite3.IntegrityError:
        row = await db.fetchone(
            "SELECT * FROM cultivators WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        return dict(row), False
    row = await db.fetchone(
        "SELECT * FROM cultivators WHERE id=?", (cursor.lastrowid,)
    )
    return dict(row), True


async def active_companions(db: Database, cultivator_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT intimacy_level FROM companions WHERE owner_id=? AND status='active'",
        (cultivator_id,),
    )
    return [dict(r) for r in rows]


async def sect_array_level(db: Database, sect_id: int | None) -> int:
    if not sect_id:
        return 0
    row = await db.fetchone("SELECT array_level FROM sects WHERE id=?", (sect_id,))
    return int(row["array_level"]) if row else 0


async def charm_count(db: Database, cultivator_id: int) -> int:
    row = await db.fetchone(
        "SELECT COUNT(*) AS c FROM dao_protection_charms"
        " WHERE owner_id=? AND consumed_at IS NULL",
        (cultivator_id,),
    )
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Sect queries
# ---------------------------------------------------------------------------

async def sect_by_name(db: Database, name: str) -> dict | None:
    row = await db.fetchone("SELECT * FROM sects WHERE name=?", (name,))
    return dict(row) if row else None


async def sect_members(db: Database, sect_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT * FROM cultivators WHERE sect_id=? ORDER BY id", (sect_id,)
    )
    return [dict(r) for r in rows]


async def sect_member_count(db: Database, sect_id: int) -> int:
    row = await db.fetchone(
        "SELECT COUNT(*) AS c FROM cultivators WHERE sect_id=?", (sect_id,)
    )
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Alchemy queries
# ---------------------------------------------------------------------------

async def recipe_by_name(db: Database, name: str) -> dict | None:
    row = await db.fetchone("SELECT * FROM alchemy_recipes WHERE LOWER(name)=LOWER(?)", (name.strip(),))
    return dict(row) if row else None


async def recipes_by_grade(db: Database, grade: str | None = None) -> list[dict]:
    if grade:
        rows = await db.fetchall("SELECT * FROM alchemy_recipes WHERE LOWER(grade)=LOWER(?) ORDER BY required_realm_tier, name", (grade.strip(),))
    else:
        rows = await db.fetchall("SELECT * FROM alchemy_recipes ORDER BY required_realm_tier, name")
    return [dict(r) for r in rows]


async def alchemy_attempts_by_cultivator(db: Database, cultivator_id: int, limit: int = 10) -> list[dict]:
    rows = await db.fetchall(
        "SELECT * FROM alchemy_attempts WHERE cultivator_id=? ORDER BY id DESC LIMIT ?",
        (cultivator_id, limit),
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Reincarnation queries
# ---------------------------------------------------------------------------

async def reincarnation_history(db: Database, cultivator_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT * FROM reincarnation_log WHERE cultivator_id=? ORDER BY id DESC",
        (cultivator_id,),
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Secret Realm queries
# ---------------------------------------------------------------------------

async def secret_realm_templates_all(db: Database) -> list[dict]:
    rows = await db.fetchall("SELECT * FROM secret_realm_templates ORDER BY min_realm_tier, id")
    return [dict(r) for r in rows]


async def secret_realm_template_by_name(db: Database, name: str) -> dict | None:
    row = await db.fetchone("SELECT * FROM secret_realm_templates WHERE LOWER(name)=LOWER(?)", (name.strip(),))
    return dict(row) if row else None


async def active_realm_run(db: Database, cultivator_id: int) -> dict | None:
    row = await db.fetchone(
        "SELECT * FROM secret_realm_runs WHERE cultivator_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (cultivator_id,),
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# World Events queries
# ---------------------------------------------------------------------------

async def active_or_upcoming_events(db: Database, guild_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT * FROM world_events WHERE guild_id=? AND status IN ('pending', 'active') ORDER BY scheduled_at",
        (guild_id,),
    )
    return [dict(r) for r in rows]


async def event_by_id(db: Database, event_id: int) -> dict | None:
    row = await db.fetchone("SELECT * FROM world_events WHERE id=?", (event_id,))
    return dict(row) if row else None


async def event_participants(db: Database, event_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT p.*, c.username FROM world_event_participants p JOIN cultivators c ON p.cultivator_id=c.id WHERE p.event_id=? ORDER BY p.damage_dealt DESC",
        (event_id,),
    )
    return [dict(r) for r in rows]


async def event_participant(db: Database, event_id: int, cultivator_id: int) -> dict | None:
    row = await db.fetchone(
        "SELECT * FROM world_event_participants WHERE event_id=? AND cultivator_id=?",
        (event_id, cultivator_id),
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Dao Laws queries
# ---------------------------------------------------------------------------

async def dao_laws_all(db: Database) -> list[dict]:
    rows = await db.fetchall("SELECT * FROM dao_laws ORDER BY realm_required, comprehension_required")
    return [dict(r) for r in rows]


async def dao_law_by_name(db: Database, name: str) -> dict | None:
    row = await db.fetchone("SELECT * FROM dao_laws WHERE LOWER(name)=LOWER(?) OR LOWER(name_zh)=LOWER(?)", (name.strip(), name.strip()))
    return dict(row) if row else None


async def cultivator_laws_all(db: Database, cultivator_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT cl.*, dl.name, dl.name_zh, dl.comprehension_required, dl.realm_required, dl.mastery_effect, dl.law_lore"
        " FROM cultivator_laws cl JOIN dao_laws dl ON cl.law_id=dl.id WHERE cl.cultivator_id=? ORDER BY cl.mastery_percentage DESC",
        (cultivator_id,),
    )
    return [dict(r) for r in rows]


async def cultivator_law(db: Database, cultivator_id: int, law_id: int) -> dict | None:
    row = await db.fetchone(
        "SELECT * FROM cultivator_laws WHERE cultivator_id=? AND law_id=?",
        (cultivator_id, law_id),
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Auction House & Trade queries
# ---------------------------------------------------------------------------

async def active_market_listings(db: Database) -> list[dict]:
    rows = await db.fetchall(
        "SELECT ml.*, c.username AS seller_name, i.name AS item_name, i.item_type, i.grade"
        " FROM market_listings ml"
        " JOIN cultivators c ON ml.seller_id=c.id"
        " JOIN items i ON ml.item_id=i.id"
        " WHERE ml.status='active' ORDER BY ml.id DESC"
    )
    return [dict(r) for r in rows]


async def market_listing_by_id(db: Database, listing_id: int) -> dict | None:
    row = await db.fetchone(
        "SELECT ml.*, c.username AS seller_name, i.name AS item_name, i.item_type, i.grade"
        " FROM market_listings ml"
        " JOIN cultivators c ON ml.seller_id=c.id"
        " JOIN items i ON ml.item_id=i.id"
        " WHERE ml.id=?",
        (listing_id,),
    )
    return dict(row) if row else None


async def active_listings_by_seller(db: Database, seller_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT ml.*, i.name AS item_name, i.item_type, i.grade"
        " FROM market_listings ml JOIN items i ON ml.item_id=i.id"
        " WHERE ml.seller_id=? AND ml.status='active'",
        (seller_id,),
    )
    return [dict(r) for r in rows]


async def pending_trade_offer(db: Database, recipient_id: int) -> dict | None:
    row = await db.fetchone(
        "SELECT t.*, c.username AS sender_name, i.name AS item_name, i.item_type, i.grade"
        " FROM trade_offers t JOIN cultivators c ON t.sender_id=c.id JOIN items i ON t.item_id=i.id"
        " WHERE t.recipient_id=? AND t.status='pending' ORDER BY t.id DESC LIMIT 1",
        (recipient_id,),
    )
    return dict(row) if row else None
