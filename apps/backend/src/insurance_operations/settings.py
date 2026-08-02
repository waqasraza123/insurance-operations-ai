from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_environment: RuntimeEnvironment


class ApiSettings(CommonSettings):
    api_host: str = Field(min_length=1)
    api_port: int = Field(ge=1, le=65_535)


class WorkerSettings(CommonSettings):
    worker_name: str = Field(min_length=1, max_length=100)
