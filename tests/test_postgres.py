"""Unit tests for PostgreSQL layer and migration tooling."""
from config.postgres import postgres_config
from core import auction as core_auc, dao_laws as core_dl


def test_postgres_config_defaults():
    assert postgres_config.is_postgres == (postgres_config.database_type in ("postgres", "postgresql"))
    assert postgres_config.min_connections >= 1
    assert postgres_config.max_connections >= postgres_config.min_connections


def test_migration_scripts_importable():
    import scripts.migrate_sqlite_to_postgres as mig
    import scripts.validate_migration as val
    import scripts.setup_discord_server as setup_srv

    assert "cultivators" in mig.TABLES
    assert "cultivators" in val.TABLES
    assert len(setup_srv.STRUCTURE) > 0


def test_postgres_schema_file_exists():
    from pathlib import Path
    schema_file = Path("migrations/postgres/011_postgres_schema.sql")
    assert schema_file.exists()
    content = schema_file.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS cultivators" in content
    assert "PARTITION BY RANGE" in content
