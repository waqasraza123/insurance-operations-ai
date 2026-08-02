from enum import StrEnum
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from insurance_operations.settings import DatabaseSettings


class DatabasePurpose(StrEnum):
    RUNTIME = "runtime"
    MIGRATION = "migration"


class DatabaseReadinessError(RuntimeError):
    pass


def psycopg_url(value: str) -> URL:
    return make_url(value).set(drivername="postgresql+psycopg")


def database_engine_options(
    settings: DatabaseSettings,
    *,
    service_name: str,
    purpose: DatabasePurpose = DatabasePurpose.RUNTIME,
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "connect_args": {
            "sslmode": settings.database_ssl_mode.value,
            "application_name": f"insurance-operations-{service_name}"[:63],
        },
    }

    if purpose is DatabasePurpose.MIGRATION:
        options["poolclass"] = NullPool
    else:
        options.update(
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
            pool_recycle=settings.database_pool_recycle_seconds,
            pool_use_lifo=True,
        )

    return options


def create_database_engine(
    settings: DatabaseSettings,
    *,
    service_name: str,
    purpose: DatabasePurpose = DatabasePurpose.RUNTIME,
) -> Engine:
    configured_url = (
        settings.migration_database_url
        if purpose is DatabasePurpose.MIGRATION
        else settings.runtime_database_url
    )
    return create_engine(
        psycopg_url(configured_url),
        **database_engine_options(
            settings,
            service_name=service_name,
            purpose=purpose,
        ),
    )


def check_database_readiness(database_engine: Engine) -> None:
    try:
        with database_engine.connect() as connection:
            result = connection.scalar(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise DatabaseReadinessError("database connection failed") from error

    if result != 1:
        raise DatabaseReadinessError("database readiness query returned no result")
