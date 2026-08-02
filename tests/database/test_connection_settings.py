import pytest
from pydantic import ValidationError
from sqlalchemy.pool import NullPool

from insurance_operations.database.connection import (
    DatabasePurpose,
    database_engine_options,
    psycopg_url,
)
from insurance_operations.settings import (
    DatabaseSettings,
    DatabaseSslMode,
    RuntimeEnvironment,
)


def build_database_settings(**overrides: object) -> DatabaseSettings:
    values: dict[str, object] = {
        "app_environment": RuntimeEnvironment.DEVELOPMENT,
        "database_url": "postgresql://user:password@pooled.example/database",
        "direct_database_url": "postgresql://user:password@direct.example/database",
        "database_ssl_mode": DatabaseSslMode.REQUIRE,
    }
    values.update(overrides)
    return DatabaseSettings.model_validate(values)


def test_runtime_and_migration_urls_remain_separate() -> None:
    settings = build_database_settings()

    assert "pooled.example" in settings.runtime_database_url
    assert "direct.example" in settings.migration_database_url
    assert psycopg_url(settings.runtime_database_url).drivername == "postgresql+psycopg"


def test_runtime_pool_uses_neon_safe_connection_options() -> None:
    settings = build_database_settings()

    options = database_engine_options(settings, service_name="api")

    assert options["pool_pre_ping"] is True
    assert options["pool_use_lifo"] is True
    assert options["pool_size"] == 5
    assert options["max_overflow"] == 2
    assert options["connect_args"] == {
        "sslmode": "require",
        "application_name": "insurance-operations-api",
    }


def test_migrations_disable_application_side_pooling() -> None:
    options = database_engine_options(
        build_database_settings(),
        service_name="alembic",
        purpose=DatabasePurpose.MIGRATION,
    )

    assert options["poolclass"] is NullPool
    assert "pool_size" not in options


def test_test_environment_requires_an_isolated_url() -> None:
    with pytest.raises(ValidationError, match="TEST_DATABASE_URL is required"):
        build_database_settings(app_environment=RuntimeEnvironment.TEST)


def test_test_environment_rejects_the_runtime_database() -> None:
    runtime_url = "postgresql://user:password@pooled.example/database"
    with pytest.raises(ValidationError, match="must be isolated"):
        build_database_settings(
            app_environment=RuntimeEnvironment.TEST,
            test_database_url=runtime_url,
        )


def test_production_rejects_disabled_ssl() -> None:
    with pytest.raises(ValidationError, match="SSL cannot be disabled"):
        build_database_settings(
            app_environment=RuntimeEnvironment.PRODUCTION,
            database_ssl_mode=DatabaseSslMode.DISABLE,
        )


def test_non_postgresql_urls_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must use PostgreSQL"):
        build_database_settings(database_url="sqlite:///local.db")
