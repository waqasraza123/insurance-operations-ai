import argparse
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from insurance_operations.database.connection import create_database_engine
from insurance_operations.database.models import Agency
from insurance_operations.settings import DatabaseSettings, RuntimeEnvironment


DEVELOPMENT_AGENCY_ID = UUID("00000000-0000-4000-8000-000000000001")
DEVELOPMENT_AGENCY_NAME = "Development Agency"


def seed_development_agency(settings: DatabaseSettings) -> bool:
    if settings.app_environment is not RuntimeEnvironment.DEVELOPMENT:
        raise ValueError("development seed requires APP_ENVIRONMENT=development")

    database_engine = create_database_engine(settings, service_name="development-seed")
    try:
        statement = (
            insert(Agency)
            .values(
                id=DEVELOPMENT_AGENCY_ID,
                name=DEVELOPMENT_AGENCY_NAME,
            )
            .on_conflict_do_nothing(index_elements=[Agency.id])
            .returning(Agency.id)
        )
        with database_engine.begin() as connection:
            return connection.scalar(statement) is not None
    finally:
        database_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="insurance-operations-seed-development")
    try:
        created = seed_development_agency(DatabaseSettings())
    except (ValueError, SQLAlchemyError) as error:
        parser.exit(1, f"development seed failed: {type(error).__name__}\n")

    result = "created" if created else "already exists"
    print(f"development agency: {result}")


if __name__ == "__main__":
    main()
