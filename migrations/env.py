from logging.config import fileConfig

from alembic import context

from insurance_operations.database.connection import (
    DatabasePurpose,
    create_database_engine,
    psycopg_url,
)
from insurance_operations.database.models import Base
from insurance_operations.settings import DatabaseSettings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    settings = DatabaseSettings()
    context.configure(
        url=psycopg_url(settings.migration_database_url).render_as_string(
            hide_password=False
        ),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = DatabaseSettings()
    database_engine = create_database_engine(
        settings,
        service_name="alembic",
        purpose=DatabasePurpose.MIGRATION,
    )

    try:
        with database_engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                transaction_per_migration=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        database_engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
