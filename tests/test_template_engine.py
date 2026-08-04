"""Tests for the narrative template engine and seed loader."""
import asyncio
import tempfile
from pathlib import Path

from core.template_engine import TemplateEngine
from db.database import Database, run_migrations
from db.seeds import seed_templates_if_empty


def _make_db(tmp: Path) -> Database:
    db = Database(tmp / "test.db")
    return db


def test_render_and_fallback():
    async def main() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db = _make_db(Path(d))
            await db.connect()
            await run_migrations(db)
            await db.execute(
                "INSERT INTO narrative_templates (category, fragment, weight)"
                " VALUES (?,?,?)",
                ("cultivate", "Hello {name} of {realm}!", 1.0),
            )
            engine = TemplateEngine(db)
            await engine.load()
            # All kwargs supplied -> substituted
            out = await engine.get("cultivate", name="Riel", realm="Qi Condensation")
            assert "Riel" in out and "Qi Condensation" in out
            # Missing kwarg -> token kept intact (no crash)
            out2 = await engine.get("cultivate")
            assert "{name}" in out2
            # Unknown category -> non-empty fallback string
            fb = await engine.get("nonexistent_category", name="Riel")
            assert isinstance(fb, str) and fb
            await db.close()

    asyncio.run(main())


def test_seed_from_json_and_idempotent():
    async def main() -> None:
        from config import default as config

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            db = _make_db(Path(d))
            await db.connect()
            await run_migrations(db)
            n1 = await seed_templates_if_empty(db, config.TEMPLATES_DIR)
            assert n1 > 0
            n2 = await seed_templates_if_empty(db, config.TEMPLATES_DIR)
            assert n2 == 0  # already seeded
            engine = TemplateEngine(db)
            await engine.load()
            frag = await engine.get("cultivate", name="Tester")
            assert isinstance(frag, str) and "Tester" in frag
            await db.close()

    asyncio.run(main())
