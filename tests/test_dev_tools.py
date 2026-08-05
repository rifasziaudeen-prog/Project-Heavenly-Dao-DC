"""Tests for the developer-experience scripts (scripts/new_feature.py)."""
import tempfile
from pathlib import Path

from scripts import new_feature as nf

SAMPLE_TEST = """\
def test_migrations():\n    assert applied == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20]\n    assert {r["version"] for r in rows} == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20}\n"""


def test_next_migration_version_empty_dir():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        assert nf.next_migration_version(Path(d)) == 1


def test_next_migration_version_scans_existing():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        Path(d, "003_sects.sql").touch()
        Path(d, "007_secret_realms.sql").touch()
        Path(d, "not_a_migration.txt").touch()
        assert nf.next_migration_version(Path(d)) == 8


def test_create_migration_path_and_content():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        Path(d, "005_alchemy.sql").touch()
        path = nf.create_migration(Path(d), "array_burst")
        assert path.name == "006_array_burst.sql"
        assert "Migration 006" in path.read_text(encoding="utf-8")
        # Idempotent: creating again does not bump the version.
        assert nf.create_migration(Path(d), "array_burst") == path


def test_patch_version_lists_adds_new_version():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        test_file = Path(d, "test_migrations.py")
        test_file.write_text(SAMPLE_TEST, encoding="utf-8")
        warnings = nf.patch_version_lists(test_file, 21)
        assert warnings == []
        patched = test_file.read_text(encoding="utf-8")
        assert "applied == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]" in patched
        assert "== {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21}" in patched


def test_patch_version_lists_warns_when_missing():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        test_file = Path(d, "test_migrations.py")
        test_file.write_text("assert something_else == True\n", encoding="utf-8")
        warnings = nf.patch_version_lists(test_file, 21)
        assert len(warnings) == 2
        # No partial writes happened.
        assert test_file.read_text(encoding="utf-8") == "assert something_else == True\n"


def test_cli_dry_run_accepts_snake_case():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        rc = nf.main([
            "array_burst", "--dry-run", "--migrations-dir", str(Path(d)),
            "--test-file", str(Path(d, "test_migrations.py")),
        ])
        assert rc == 0
        assert list(Path(d).glob("*.sql")) == []  # dry-run writes nothing


def test_cli_rejects_bad_name():
    assert nf.main(["Bad Name!", "--dry-run"]) == 1
