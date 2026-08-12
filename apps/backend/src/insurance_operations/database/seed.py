import argparse
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from insurance_operations.database.connection import create_database_engine
from insurance_operations.database.models import (
    Agency,
    AgencyApprovedFaq,
    AgencyMembership,
    AgencyReceptionistSettings,
    AppUser,
)
from insurance_operations.database.models.identity import AgencyEnvironment
from insurance_operations.settings import DatabaseSettings, RuntimeEnvironment

DEVELOPMENT_AGENCY_ID = UUID("00000000-0000-4000-8000-000000000001")
DEVELOPMENT_AGENCY_NAME = "Development Agency"
DEVELOPMENT_AGENCY_SLUG = "development-agency"
DEVELOPMENT_ACTOR_USER_ID = UUID("00000000-0000-4000-8000-000000000002")
DEVELOPMENT_ACTOR_AUTH_SUBJECT = UUID("00000000-0000-4000-8000-000000000003")
DEVELOPMENT_MEMBERSHIP_ID = UUID("00000000-0000-4000-8000-000000000004")
DEVELOPMENT_RECEPTIONIST_SETTINGS_ID = UUID("00000000-0000-4000-8000-000000000005")
DEVELOPMENT_APPROVED_FAQ_IDS = (
    UUID("00000000-0000-4000-8000-000000000006"),
    UUID("00000000-0000-4000-8000-000000000007"),
    UUID("00000000-0000-4000-8000-000000000008"),
)
DEVELOPMENT_ACTOR_DISPLAY_NAME = "Synthetic Voice AI Tester"
DEVELOPMENT_RECEPTIONIST_PUBLIC_NAME = "Harborline Insurance"


@dataclass(frozen=True)
class DevelopmentSeedResult:
    agency_created: bool
    actor_created: bool
    membership_created: bool
    receptionist_settings_created: bool
    approved_faqs_created: int


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
        receptionist_settings_statement = (
            insert(AgencyReceptionistSettings)
            .values(
                id=DEVELOPMENT_RECEPTIONIST_SETTINGS_ID,
                agency_id=DEVELOPMENT_AGENCY_ID,
                public_name=DEVELOPMENT_RECEPTIONIST_PUBLIC_NAME,
                greeting=(
                    "Thanks for contacting Harborline Insurance. I'm the AI "
                    "receptionist for this synthetic demonstration."
                ),
                office_hours=("Monday through Friday, 9:00 AM to 5:00 PM Eastern Time"),
                contact_email="receptionist@example.com",
                contact_phone="+1 555 010 0142",
                supported_insurance_categories=[
                    "Auto",
                    "Homeowners",
                    "Renters",
                    "Small business",
                ],
                escalation_message=(
                    "A licensed team member will follow up for quotes, coverage "
                    "advice, binding, claims, or any request I cannot safely answer."
                ),
                created_by=DEVELOPMENT_ACTOR_USER_ID,
                updated_by=DEVELOPMENT_ACTOR_USER_ID,
            )
            .on_conflict_do_nothing(constraint="uq_agency_receptionist_settings_agency")
            .returning(AgencyReceptionistSettings.id)
        )
        approved_faq_statements = [
            insert(AgencyApprovedFaq)
            .values(
                id=faq_id,
                agency_id=DEVELOPMENT_AGENCY_ID,
                question=question,
                normalized_question=normalized_question,
                approved_answer=approved_answer,
                status="ACTIVE",
                created_by=DEVELOPMENT_ACTOR_USER_ID,
                updated_by=DEVELOPMENT_ACTOR_USER_ID,
            )
            .on_conflict_do_nothing(
                constraint="uq_agency_approved_faqs_agency_question"
            )
            .returning(AgencyApprovedFaq.id)
            for faq_id, question, normalized_question, approved_answer in (
                (
                    DEVELOPMENT_APPROVED_FAQ_IDS[0],
                    "What are your office hours?",
                    "what are your office hours",
                    "Our office is open Monday through Friday from 9:00 AM "
                    "to 5:00 PM Eastern Time.",
                ),
                (
                    DEVELOPMENT_APPROVED_FAQ_IDS[1],
                    "What types of insurance can your agency help with?",
                    "what types of insurance can your agency help with",
                    "Our synthetic showcase handles new inquiries about auto, "
                    "homeowners, renters, and small business insurance.",
                ),
                (
                    DEVELOPMENT_APPROVED_FAQ_IDS[2],
                    "How can I get an insurance quote?",
                    "how can i get an insurance quote",
                    "I can collect your contact details and insurance interest. "
                    "A licensed team member must discuss and provide any quote.",
                ),
            )
        ]
        with database_engine.begin() as connection:
            agency_created = connection.scalar(agency_statement) is not None
            actor_created = connection.scalar(actor_statement) is not None
            membership_created = connection.scalar(membership_statement) is not None
            receptionist_settings_created = (
                connection.scalar(receptionist_settings_statement) is not None
            )
            approved_faqs_created = sum(
                connection.scalar(statement) is not None
                for statement in approved_faq_statements
            )
            return DevelopmentSeedResult(
                agency_created=agency_created,
                actor_created=actor_created,
                membership_created=membership_created,
                receptionist_settings_created=receptionist_settings_created,
                approved_faqs_created=approved_faqs_created,
            )
    finally:
        database_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="insurance-operations-seed-development")
    try:
        result = seed_development_foundation(DatabaseSettings())
    except (ValueError, SQLAlchemyError) as error:
        parser.exit(1, f"development seed failed: {type(error).__name__}\n")

    created_count = (
        sum(
            (
                result.agency_created,
                result.actor_created,
                result.membership_created,
                result.receptionist_settings_created,
            )
        )
        + result.approved_faqs_created
    )
    print(f"development foundation: {created_count} record(s) created")


if __name__ == "__main__":
    main()
