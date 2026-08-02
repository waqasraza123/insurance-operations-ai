from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
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
            and any(
                database_target(self.test_database_url) == database_target(url)
                for url in (self.database_url, self.direct_database_url)
                if url is not None
            )
        ):
            raise ValueError(
                "TEST_DATABASE_URL must be isolated from database runtime and "
                "migration URLs"
            )
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
    web_origin: str = "http://localhost:3000"
    idempotency_retention_hours: int = Field(default=24, ge=1, le=168)
    conversation_ai_enabled: bool = False
    development_actor_user_id: UUID | None = None
    conversation_max_duration_seconds: int = Field(default=180, ge=1, le=180)
    conversation_daily_session_limit: int = Field(default=10, ge=1, le=10)
    conversation_confirmation_window_minutes: int = Field(default=30, ge=5, le=60)
    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_agent_id: str | None = Field(default=None, min_length=1, max_length=200)
    elevenlabs_privacy_confirmed: bool = False

    @field_validator("web_origin")
    @classmethod
    def validate_web_origin(cls, value: str) -> str:
        parsed_origin = urlsplit(value)
        if (
            parsed_origin.scheme not in {"http", "https"}
            or parsed_origin.hostname is None
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise ValueError("WEB_ORIGIN must be an HTTP or HTTPS origin")
        return value.rstrip("/")

    @field_validator("elevenlabs_agent_id")
    @classmethod
    def normalize_agent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("ELEVENLABS_AGENT_ID cannot be empty")
        return normalized_value

    @field_validator("elevenlabs_api_key")
    @classmethod
    def normalize_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        return SecretStr(value.get_secret_value().strip())

    @model_validator(mode="after")
    def validate_conversation_configuration(self) -> Self:
        if not self.conversation_ai_enabled:
            return self
        if self.app_environment is not RuntimeEnvironment.DEVELOPMENT:
            raise ValueError("conversation AI can be enabled only in development")
        if self.development_actor_user_id is None:
            raise ValueError(
                "DEVELOPMENT_ACTOR_USER_ID is required when conversation AI is enabled"
            )
        if (
            self.elevenlabs_api_key is None
            or not self.elevenlabs_api_key.get_secret_value().strip()
        ):
            raise ValueError(
                "ELEVENLABS_API_KEY is required when conversation AI is enabled"
            )
        if self.elevenlabs_agent_id is None:
            raise ValueError(
                "ELEVENLABS_AGENT_ID is required when conversation AI is enabled"
            )
        if not self.elevenlabs_privacy_confirmed:
            raise ValueError(
                "ElevenLabs audio saving and zero-day retention must be confirmed"
            )
        return self


class WorkerSettings(DatabaseSettings):
    worker_name: str = Field(min_length=1, max_length=100)


def database_target(value: str) -> tuple[str | None, int, str | None]:
    parsed_url = make_url(value)
    host = parsed_url.host.lower() if parsed_url.host is not None else None
    if host is not None:
        first_label, separator, remaining_labels = host.partition(".")
        host = first_label.removesuffix("-pooler") + separator + remaining_labels
    return (
        host,
        parsed_url.port or 5432,
        parsed_url.database,
    )
