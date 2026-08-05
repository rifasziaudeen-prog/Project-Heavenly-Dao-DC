"""check_docs.py — drift-linter for the docs that used to go stale by hand.

Run before committing (or whenever):

    python scripts/check_docs.py            # all checks
    python scripts/check_docs.py --quick    # skip the pytest collection

Checks:
  1. README test count  ==  actual collected pytest tests
  2. README command table  <->  app_commands registered in cogs/
     (missing rows = undocumented commands; extra rows = stale docs)
  3. CHANGELOG.md versions are newest-first (semver strictly descending)
  4. tests/test_migrations.py version lists match the migrations/ dir

Exit code: 0 = clean, 2 = drift found (argparse errors also exit 2).
Pure parsing helpers are exported for unit tests (tests/test_dev_tools.py).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COGS_DIR = PROJECT_ROOT / "cogs"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
MIGRATION_TEST = PROJECT_ROOT / "tests" / "test_migrations.py"
README = PROJECT_ROOT / "README.md"
CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


# --------------------------------------------------------------------------- check 1: tests
def readme_test_count(readme_text: str) -> int | None:
    match = re.search(r"pytest suite \((\d+) tests", readme_text)
    return int(match.group(1)) if match else None


def collect_test_count(python: str, root: Path, timeout: int = 120) -> int | None:
    """Collect the real pytest count (None if collection failed)."""
    proc = subprocess.run(
        [python, "-m", "pytest", "--collect-only", "-q"],
        cwd=root, capture_output=True, text=True, timeout=timeout,
    )
    match = re.search(r"(\d+) tests? collected", proc.stdout + proc.stderr)
    return int(match.group(1)) if match else None


# --------------------------------------------------------------------------- check 2: commands
def commands_in_code(cogs_dir: Path) -> set[str]:
    names: set[str] = set()
    for path in sorted(cogs_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        names |= set(re.findall(r"app_commands\.command\(\s*name=\"([a-z_]+)\"", text))
    return names


def readme_commands(readme_text: str) -> set[str]:
    """Slash-command names documented in the README Commands table.

    One row may document several commands (`/trade_accept` / `/trade_decline`),
    so every `/name` in every table row (line starting with '|') counts.
    """
    section = readme_text.split("## Commands", 1)
    if len(section) < 2:
        return set()
    section = section[1].split("\n## ", 1)[0]
    names: set[str] = set()
    for line in section.splitlines():
        if line.lstrip().startswith("|"):
            names |= set(re.findall(r"`/([a-z_]+)", line))
    return names


# --------------------------------------------------------------------------- check 3: changelog
def changelog_versions(changelog_text: str) -> list[tuple[int, int, int]]:
    return [
        tuple(int(x) for x in m.groups())
        for m in re.finditer(r"^## \[(\d+)\.(\d+)\.(\d+)\]", changelog_text, re.MULTILINE)
    ]


def changelog_order_errors(versions: list[tuple[int, int, int]]) -> list[str]:
    """Newest-first rule: each version must be < the one above it."""
    errors = []
    for above, below in zip(versions, versions[1:]):
        if below >= above:
            errors.append(
                f"CHANGELOG order broken: [{below[0]}.{below[1]}.{below[2]}] "
                f"sits below [{above[0]}.{above[1]}.{above[2]}] but must be older"
            )
    return errors


# --------------------------------------------------------------------------- check 4: migrations
def migration_versions(migrations_dir: Path) -> set[int]:
    versions = set()
    for path in migrations_dir.glob("*.sql"):
        match = re.match(r"^(\d+)_", path.name)
        if match:
            versions.add(int(match.group(1)))
    return versions


def test_file_versions(test_text: str) -> set[int]:
    match = re.search(r"applied == \[([\d, ]+)\]", test_text)
    if not match:
        return set()
    return {int(x) for x in match.group(1).split(",")}


# --------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(prog="check_docs.py", description=__doc__)
    parser.add_argument("--quick", action="store_true", help="skip the pytest collection")
    args = parser.parse_args(argv)

    problems: list[str] = []
    notes: list[str] = []

    # 1 — test count
    readme_count = readme_test_count(README.read_text(encoding="utf-8"))
    if readme_count is None:
        problems.append("README has no 'pytest suite (N tests' claim to verify.")
    elif args.quick:
        notes.append(f"test count check skipped (--quick); README claims {readme_count}")
    else:
        actual = collect_test_count(sys.executable, PROJECT_ROOT)
        if actual is None:
            problems.append("Could not collect pytest test count (pytest failed?).")
        elif actual != readme_count:
            problems.append(
                f"README says {readme_count} tests but pytest collects {actual}."
            )
        else:
            notes.append(f"{actual} tests — README matches ✅")

    # 2 — command table
    code_cmds = commands_in_code(COGS_DIR)
    readme_cmds = readme_commands(README.read_text(encoding="utf-8"))
    missing = sorted(code_cmds - readme_cmds)
    stale = sorted(readme_cmds - code_cmds)
    if missing:
        problems.append(f"Commands missing from README table: {', '.join(missing)}")
    if stale:
        problems.append(f"README rows with no matching command in code: {', '.join(stale)}")
    if not missing and not stale:
        notes.append(f"{len(code_cmds)} commands documented in README ✅")

    # 3 — changelog order
    versions = changelog_versions(CHANGELOG.read_text(encoding="utf-8"))
    if not versions:
        problems.append("CHANGELOG has no '## [x.y.z]' entries to check.")
    else:
        errors = changelog_order_errors(versions)
        problems.extend(errors)
        if not errors:
            notes.append(f"CHANGELOG newest-first ✅ ({len(versions)} releases)")

    # 4 — migration version lists
    disk_versions = migration_versions(MIGRATIONS_DIR)
    test_versions = test_file_versions(MIGRATION_TEST.read_text(encoding="utf-8"))
    if not test_versions:
        problems.append("Could not find the 'applied == [...]' list in tests/test_migrations.py.")
    elif disk_versions != test_versions:
        problems.append(
            f"Migrations on disk {sorted(disk_versions)} don't match the test's "
            f"version list {sorted(test_versions)} — run scripts/new_feature.py or patch by hand."
        )
    else:
        notes.append(f"{len(disk_versions)} migrations in sync with tests ✅")

    print()
    for note in notes:
        print(f"  {note}")
    if problems:
        print()
        for p in problems:
            print(f"  ⚠️  {p}")
        print(f"\n{len(problems)} drift issue(s) found.")
        return 2
    print("\nAll docs in sync. ✨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
