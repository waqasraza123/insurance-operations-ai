from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from insurance_operations.database.connection import create_database_engine
from insurance_operations.settings import DatabaseSettings, RuntimeEnvironment


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def database_settings() -> DatabaseSettings:
    settings = DatabaseSettings()
    if settings.app_environment is not RuntimeEnvironment.TEST:
        pytest.fail("database tests require APP_ENVIRONMENT=test")
    return settings


@pytest.fixture(scope="session")
def migrated_database(database_settings: DatabaseSettings) -> Iterator[Engine]:
    alembic_config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    database_engine = create_database_engine(
        database_settings,
        service_name="migration-tests",
    )
    try:
        yield database_engine
    finally:
        database_engine.dispose()
        command.downgrade(alembic_config, "base")
