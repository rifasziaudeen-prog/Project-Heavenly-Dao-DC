"""Seed `narrative_templates` from `templates/*.json` on first startup.

JSON format: {"category": ["fragment one", "fragment two", ...]}
Adding new fragments = dropping a file (or editing one) — no code changes.
"""
from __future__ import annotations

import json
from pathlib import Path

from config import default as config
from db.database import Database


async def seed_templates_if_empty(db: Database, templates_dir: Path | None = None) -> int:
    directory = templates_dir or config.TEMPLATES_DIR
    if not directory.is_dir():
        return 0
    row = await db.fetchone("SELECT COUNT(*) AS c FROM narrative_templates")
    if row and row["c"] > 0:
        return 0

    rows: list[tuple[str, str, float]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for category, fragments in data.items():
            if not isinstance(fragments, list):
                continue
            for fragment in fragments:
                if isinstance(fragment, str) and fragment.strip():
                    rows.append((category, fragment.strip(), 1.0))
    if rows:
        await db.executemany(
            "INSERT INTO narrative_templates (category, fragment, weight)"
            " VALUES (?,?,?)",
            rows,
        )
    return len(rows)
