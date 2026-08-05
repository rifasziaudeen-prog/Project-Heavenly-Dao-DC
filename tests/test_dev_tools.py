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


# ---------------------------------------------------------------------------
# check_docs.py — pure parsers
# ---------------------------------------------------------------------------
from scripts import check_docs as cd


def test_readme_test_count():
    assert cd.readme_test_count("tests/  pytest suite (236 tests covering balance") == 236
    assert cd.readme_test_count("no claim here") is None


def test_readme_commands_only_in_commands_section():
    text = (
        "# Title\n"
        "## Commands\n"
        "| `/cultivate` | do it |\n"
        "| `/event_attack <event_id> <choice>` | fight |\n"
        "| `/sect_array_burst` | pulse |\n"
        "## Game design\n"
        "Use `/hidden_command` in prose — not a table row.\n"
    )
    assert cd.readme_commands(text) == {"cultivate", "event_attack", "sect_array_burst"}


def test_commands_in_code(tmp_path):
    (tmp_path / "a.py").write_text(
        '@app_commands.command(name="cultivate")\n'
        '@app_commands.command(\n    name="event_attack",\n    description="x")\n',
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text(
        "async def helper():\n    pass\n", encoding="utf-8"
    )
    assert cd.commands_in_code(tmp_path) == {"cultivate", "event_attack"}


def test_changelog_order():
    good = "## [1.11.0] — x\n## [1.10.0] — y\n## [1.9.0] — z\n"
    assert cd.changelog_order_errors(cd.changelog_versions(good)) == []

    bad = "## [1.9.0] — x\n## [1.11.0] — y\n## [1.10.0] — z\n"
    errors = cd.changelog_order_errors(cd.changelog_versions(bad))
    assert len(errors) == 1 and "1.11.0" in errors[0]


def test_migration_version_parsers(tmp_path):
    (tmp_path / "003_sects.sql").touch()
    (tmp_path / "007_x.sql").touch()
    assert cd.migration_versions(tmp_path) == {3, 7}

    test_text = 'assert applied == [1, 2, 3, 4, 5, 6, 7]\n'
    assert cd.test_file_versions(test_text) == {1, 2, 3, 4, 5, 6, 7}
    assert cd.test_file_versions("nothing here") == set()


def test_patch_version_lists_idempotent_no_duplicates():
    """Re-running the scaffolder for the same feature must not duplicate a version."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        test_file = Path(d, "test_migrations.py")
        test_file.write_text(SAMPLE_TEST, encoding="utf-8")
        assert nf.patch_version_lists(test_file, 21) == []
        assert nf.patch_version_lists(test_file, 21) == []  # second run
        patched = test_file.read_text(encoding="utf-8")
        assert patched.count("21") == 2  # once in each list, never twice
        assert "20, 21]" in patched and "21, 21]" not in patched
