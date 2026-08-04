"""config/postgres.py

PostgreSQL configuration settings and connection helpers.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/heavenly_dao")
    database_type: str = os.getenv("DATABASE_TYPE", "sqlite").lower()
    min_connections: int = int(os.getenv("DB_MIN_CONNECTIONS", "5"))
    max_connections: int = int(os.getenv("DB_MAX_CONNECTIONS", "20"))
    command_timeout: int = int(os.getenv("DB_COMMAND_TIMEOUT", "60"))

    @property
    def is_postgres(self) -> bool:
        return self.database_type in ("postgres", "postgresql")


postgres_config = PostgresConfig()
