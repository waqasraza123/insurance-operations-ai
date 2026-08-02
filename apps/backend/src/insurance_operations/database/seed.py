import argparse
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from insurance_operations.database.connection import create_database_engine
from insurance_operations.database.models import Agency, AgencyMembership, AppUser
from insurance_operations.database.models.identity import AgencyEnvironment
from insurance_operations.settings import DatabaseSettings, RuntimeEnvironment

DEVELOPMENT_AGENCY_ID = UUID("00000000-0000-4000-8000-000000000001")
DEVELOPMENT_AGENCY_NAME = "Development Agency"
DEVELOPMENT_AGENCY_SLUG = "development-agency"
DEVELOPMENT_ACTOR_USER_ID = UUID("00000000-0000-4000-8000-000000000002")
DEVELOPMENT_ACTOR_AUTH_SUBJECT = UUID("00000000-0000-4000-8000-000000000003")
DEVELOPMENT_MEMBERSHIP_ID = UUID("00000000-0000-4000-8000-000000000004")
DEVELOPMENT_ACTOR_DISPLAY_NAME = "Synthetic Voice AI Tester"


@dataclass(frozen=True)
class DevelopmentSeedResult:
    agency_created: bool
    actor_created: bool
    membership_created: bool


def seed_development_foundation(settings: DatabaseSettings) -> DevelopmentSeedResult:
    if settings.app_environment is not RuntimeEnvironment.DEVELOPMENT:
        raise ValueError("development seed requires APP_ENVIRONMENT=development")

    database_engine = create_database_engine(settings, service_name="development-seed")
    try:
        agency_statement = (
            insert(Agency)
            .values(
                id=DEVELOPMENT_AGENCY_ID,
                name=DEVELOPMENT_AGENCY_NAME,
                slug=DEVELOPMENT_AGENCY_SLUG,
                environment_kind=AgencyEnvironment.DEVELOPMENT.value,
            )
            .on_conflict_do_nothing(index_elements=[Agency.id])
            .returning(Agency.id)
        )
        actor_statement = (
            insert(AppUser)
            .values(
                id=DEVELOPMENT_ACTOR_USER_ID,
                auth_subject=DEVELOPMENT_ACTOR_AUTH_SUBJECT,
                display_name=DEVELOPMENT_ACTOR_DISPLAY_NAME,
            )
            .on_conflict_do_nothing(index_elements=[AppUser.id])
            .returning(AppUser.id)
        )
        membership_statement = (
            insert(AgencyMembership)
            .values(
                id=DEVELOPMENT_MEMBERSHIP_ID,
                agency_id=DEVELOPMENT_AGENCY_ID,
                app_user_id=DEVELOPMENT_ACTOR_USER_ID,
            )
            .on_conflict_do_nothing(index_elements=[AgencyMembership.id])
            .returning(AgencyMembership.id)
        )
        with database_engine.begin() as connection:
            agency_created = connection.scalar(agency_statement) is not None
            actor_created = connection.scalar(actor_statement) is not None
            membership_created = connection.scalar(membership_statement) is not None
            return DevelopmentSeedResult(
                agency_created=agency_created,
                actor_created=actor_created,
                membership_created=membership_created,
            )
    finally:
        database_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="insurance-operations-seed-development")
    try:
        result = seed_development_foundation(DatabaseSettings())
    except (ValueError, SQLAlchemyError) as error:
        parser.exit(1, f"development seed failed: {type(error).__name__}\n")

    created_count = sum(
        (
            result.agency_created,
            result.actor_created,
            result.membership_created,
        )
    )
    print(f"development foundation: {created_count} record(s) created")


if __name__ == "__main__":
    main()
