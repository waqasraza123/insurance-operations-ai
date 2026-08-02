from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class RuntimeEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class DatabaseSslMode(StrEnum):
    DISABLE = "disable"
    REQUIRE = "require"
    VERIFY_CA = "verify-ca"
    VERIFY_FULL = "verify-full"


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_environment: RuntimeEnvironment


class DatabaseSettings(CommonSettings):
    database_url: str
    direct_database_url: str | None = None
    test_database_url: str | None = None
    database_ssl_mode: DatabaseSslMode = DatabaseSslMode.REQUIRE
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=2, ge=0, le=20)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=60)
    database_pool_recycle_seconds: int = Field(default=300, ge=30, le=3_600)

    @field_validator(
        "database_url",
        "direct_database_url",
        "test_database_url",
    )
    @classmethod
    def validate_postgresql_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        try:
            parsed_url = make_url(value)
        except ArgumentError as error:
            raise ValueError("database URLs must be valid PostgreSQL URLs") from error
        if parsed_url.drivername not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError("database URLs must use PostgreSQL with psycopg")
        if not parsed_url.database:
            raise ValueError("database URLs must include a database name")
        return value

    @model_validator(mode="after")
    def validate_database_environment(self) -> Self:
        if (
            self.app_environment is RuntimeEnvironment.TEST
            and self.test_database_url is None
        ):
            raise ValueError("TEST_DATABASE_URL is required in the test environment")
        if (
            self.app_environment is RuntimeEnvironment.TEST
            and self.test_database_url is not None
            and database_target(self.test_database_url)
            == database_target(self.database_url)
        ):
            raise ValueError("TEST_DATABASE_URL must be isolated from DATABASE_URL")
        if (
            self.app_environment is RuntimeEnvironment.PRODUCTION
            and self.database_ssl_mode is DatabaseSslMode.DISABLE
        ):
            raise ValueError("database SSL cannot be disabled in production")
        return self

    @property
    def runtime_database_url(self) -> str:
        if self.app_environment is RuntimeEnvironment.TEST:
            if self.test_database_url is None:
                raise RuntimeError("test database configuration is unavailable")
            return self.test_database_url
        return self.database_url

    @property
    def migration_database_url(self) -> str:
        if self.app_environment is RuntimeEnvironment.TEST:
            return self.runtime_database_url
        return self.direct_database_url or self.database_url


class ApiSettings(DatabaseSettings):
    api_host: str = Field(min_length=1)
    api_port: int = Field(ge=1, le=65_535)


class WorkerSettings(DatabaseSettings):
    worker_name: str = Field(min_length=1, max_length=100)


def database_target(value: str) -> tuple[str | None, int, str | None]:
    parsed_url = make_url(value)
    return (
        parsed_url.host.lower() if parsed_url.host is not None else None,
        parsed_url.port or 5432,
        parsed_url.database,
    )
