"""db/postgres.py

Async PostgreSQL connection pool wrapper using asyncpg.
Compatible interface with db/database.py for seamless database switching.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, List, Optional, Tuple

try:
    import asyncpg
except ImportError:
    asyncpg = None

_pool: Optional[Any] = None


async def init_pool(database_url: str, min_size: int = 5, max_size: int = 20) -> Any:
    """Initialize asyncpg connection pool."""
    global _pool
    if asyncpg is None:
        raise RuntimeError("asyncpg package is required for PostgreSQL support. Install via `pip install asyncpg`.")
    
    _pool = await asyncpg.create_pool(
        database_url,
        min_size=min_size,
        max_size=max_size,
        command_timeout=60,
        server_settings={"jit": "off"},
    )
    return _pool


async def close_pool() -> None:
    """Close asyncpg connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection():
    """Acquire connection from connection pool."""
    if _pool is None:
        raise RuntimeError("PostgreSQL pool is not initialized. Call init_pool() first.")
    async with _pool.acquire() as conn:
        yield conn


async def fetch_one(query: str, *args) -> Optional[dict]:
    """Fetch single row as dictionary."""
    async with get_connection() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_many(query: str, *args) -> List[dict]:
    """Fetch multiple rows as dictionaries."""
    async with get_connection() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def execute(query: str, *args) -> str:
    """Execute SQL query."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def execute_many(query: str, args_list: List[Tuple[Any, ...]]) -> None:
    """Execute query with batch arguments."""
    async with get_connection() as conn:
        await conn.executemany(query, args_list)
