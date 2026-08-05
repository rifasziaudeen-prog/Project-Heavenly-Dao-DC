"""new_feature.py — scaffold a new feature with zero boilerplate.

Usage (from the repo root):

    python scripts/new_feature.py sect_array_burst          # create + patch
    python scripts/new_feature.py world_boss --dry-run      # preview only

What it does:
  1. Picks the next free migration version (max NNN + 1) and creates
     ``migrations/NNN_<name>.sql`` with a header template.
  2. Patches the hardcoded version lists in ``tests/test_migrations.py``
     (the "applied == [...]" and rerun "== {…}" assertions) so a new
     migration never breaks the suite again. Idempotent — re-running for
     the same name never duplicates a version.
  3. Prints the rest-of-the-feature checklist (Postgres parity, core stub,
     cog command, tests, docs) so nothing is forgotten.

Pure helpers are exported for unit tests (tests/test_dev_tools.py).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
MIGRATION_TEST = PROJECT_ROOT / "tests" / "test_migrations.py"

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# --------------------------------------------------------------------------- pure helpers
def next_migration_version(migrations_dir: Path) -> int:
    """The next free migration version: max existing NNN + 1 (1 if none)."""
    highest = 0
    if migrations_dir.is_dir():
        for path in migrations_dir.glob("*.sql"):
            match = re.match(r"^(\d+)_", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest + 1


def new_migration_path(migrations_dir: Path, name: str) -> Path:
    """Path for the new migration file (version auto-numbered)."""
    version = next_migration_version(migrations_dir)
    return migrations_dir / f"{version:03d}_{name}.sql"


MIGRATION_TEMPLATE = """\
-- Migration {version:03d}: {title}
--
-- What this feature does (one or two sentences). Every balance number it
-- introduces belongs in a named constant inside core/*.py — never a magic
-- number here or in a cog. Column additions are ALTER TABLE ... ADD COLUMN;
-- the runner tolerates re-runs ("duplicate column name" is skipped).
"""


def _sentence_case(name: str) -> str:
    return name.replace("_", " ").capitalize()


def create_migration(migrations_dir: Path, name: str) -> Path:
    """Create and return the new migration file (no-op if it already exists)."""
    # Idempotent: if a migration for this name already exists, return it.
    existing = sorted(migrations_dir.glob(f"*_{name}.sql"))
    if existing:
        return existing[0]
    path = new_migration_path(migrations_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = MIGRATION_TEMPLATE.format(
        version=next_migration_version(migrations_dir), title=_sentence_case(name)
    )
    path.write_text(body, encoding="utf-8")
    return path


def _ensure_in_list(
    text: str, pattern: str, version: int, closing: str
) -> tuple[str, bool]:
    """Return (text, ok) with `version` guaranteed inside the matched list.

    Idempotent: if the version is already present, the text is untouched —
    re-running the scaffolder for the same feature can never duplicate it.
    ``ok`` is False only when the pattern itself is missing.
    """
    match = re.search(pattern, text)
    if not match:
        return text, False
    numbers = {int(x) for x in re.findall(r"\d+", match.group(1))}
    if version in numbers:
        return text, True
    return (
        text[: match.end(1)] + f", {version}{closing}" + text[match.end(1) + 1:]
    ), True


def patch_version_lists(test_file: Path, version: int) -> list[str]:
    """Add `version` to the hardcoded version assertions; returns warnings."""
    if not test_file.exists():
        return [f"⚠️  {test_file} not found — patch version lists manually."]
    text = test_file.read_text(encoding="utf-8")
    original = text

    # 1) "assert applied == [1, 2, …]"
    text, n_list = _ensure_in_list(
        text, r"(applied == \[[\d, ]+)\]", version, "]"
    )
    # 2) "assert {r[\"version\"] for r in rows} == {1, 2, …}"
    text, n_set = _ensure_in_list(
        text, r"(== \{[0-9, ]+)\}", version, "}"
    )

    if text != original:
        test_file.write_text(text, encoding="utf-8")

    warnings: list[str] = []
    if not n_list:
        warnings.append("⚠️  Could not find the 'applied == [...]' assertion to patch.")
    if not n_set:
        warnings.append("⚠️  Could not find the rerun version-set assertion to patch.")
    return warnings


# --------------------------------------------------------------------------- checklist
CHECKLIST = """\
✅ Created {migration}
✅ Patched the version assertions in tests/test_migrations.py

Still to do (the rest of a feature — see BALANCE.md for where numbers live):
  1. Fill in the migration body (tables / ALTER TABLE ... ADD COLUMN).
  2. Postgres parity: mirror new columns in migrations/postgres/011_postgres_schema.sql.
  3. Core engine: pure logic + named constants in core/<system>.py.
  4. Cog: the command + thin glue in cogs/<system>.py (embed, validation).
  5. Tests: unit tests for the core logic; update test_migrations.py column checks.
  6. Docs: CHANGELOG.md (newest-first), README.md command table + roadmap,
     MIGRATION.md if relevant.
  7. Run: python -m pytest -q   (suite must stay green)
  8. Run: python scripts/check_docs.py   (docs must stay in sync)
"""


# --------------------------------------------------------------------------- CLI
def _ensure_utf8_stdio() -> None:
    """Windows consoles default to cp1252 and choke on emoji — force UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        prog="new_feature.py",
        description="Scaffold a new feature: migration + version-list patch.",
    )
    parser.add_argument("name", help="lowercase_snake_case feature name, e.g. sect_array_burst")
    parser.add_argument(
        "--dry-run", action="store_true", help="preview the migration path without writing"
    )
    parser.add_argument(
        "--migrations-dir", type=Path, default=MIGRATIONS_DIR, help="override migrations dir (tests)"
    )
    parser.add_argument(
        "--test-file", type=Path, default=MIGRATION_TEST, help="override the migration test file (tests)"
    )
    args = parser.parse_args(argv)

    if not NAME_RE.match(args.name):
        print(f"❌ Name must match {NAME_RE.pattern} (lowercase snake_case).")
        return 1

    path = new_migration_path(args.migrations_dir, args.name)
    print(f"📦 Migration would be: {path}")
    if args.dry_run:
        print("(dry-run — nothing written)")
        return 0

    created = create_migration(args.migrations_dir, args.name)
    warnings = patch_version_lists(args.test_file, int(created.name.split("_", 1)[0]))

    print(CHECKLIST.format(migration=created))
    for w in warnings:
        print(w)
    return 0 if not warnings else 2


if __name__ == "__main__":
    sys.exit(main())
