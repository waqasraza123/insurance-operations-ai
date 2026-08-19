import argparse
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from insurance_operations.database.connection import create_database_engine
from insurance_operations.database.models import (
    Agency,
    AgencyApprovedFaq,
    AgencyCallPolicy,
    AgencyInboundNumber,
    AgencyMembership,
    AgencyReceptionistSettings,
    AppUser,
    InboundNumberStatus,
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
DEVELOPMENT_CALL_POLICY_ID = UUID("00000000-0000-4000-8000-000000000009")
DEVELOPMENT_INBOUND_NUMBER_ID = UUID("00000000-0000-4000-8000-000000000010")
DEVELOPMENT_ACTOR_DISPLAY_NAME = "Synthetic Voice AI Tester"
DEVELOPMENT_RECEPTIONIST_PUBLIC_NAME = "Harborline Insurance"


@dataclass(frozen=True)
class DevelopmentSeedResult:
    agency_created: bool
    actor_created: bool
    membership_created: bool
    receptionist_settings_created: bool
    approved_faqs_created: int
    call_policy_configured: bool = False
    inbound_number_configured: bool = False


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
        call_policy_configured, inbound_number_configured = configure_demo_telephony(
            database_engine, settings
        )
        return DevelopmentSeedResult(
            agency_created=agency_created,
            actor_created=actor_created,
            membership_created=membership_created,
            receptionist_settings_created=receptionist_settings_created,
            approved_faqs_created=approved_faqs_created,
            call_policy_configured=call_policy_configured,
            inbound_number_configured=inbound_number_configured,
        )
    finally:
        database_engine.dispose()


def configure_demo_telephony(
    database_engine: Engine,
    settings: DatabaseSettings,
) -> tuple[bool, bool]:
    inbound_number = settings.demo_inbound_number_e164
    transfer_destination = settings.demo_transfer_destination_e164
    if inbound_number is None and transfer_destination is None:
        return False, False
    if inbound_number is None or transfer_destination is None:
        raise ValueError("demo telephony seed requires both demo phone-number settings")

    availability_windows = [
        {
            "weekday": weekday,
            "start_local": "00:00",
            "end_local": "23:59",
        }
        for weekday in range(7)
    ]
    policy_values: dict[str, object] = {
        "inbound_enabled": True,
        "timezone": "UTC",
        "availability_windows": availability_windows,
        "transfer_enabled": True,
        "transfer_destination_e164": transfer_destination,
        "transfer_ring_timeout_seconds": 20,
        "max_concurrent_calls": 2,
        "daily_call_limit": 10,
        "callback_fallback_enabled": True,
        "after_hours_message": (
            "The synthetic demo team is unavailable and will follow up."
        ),
        "unavailable_message": (
            "The synthetic demo team could not answer and will follow up."
        ),
        "updated_by": DEVELOPMENT_ACTOR_USER_ID,
    }
    with Session(database_engine) as session, session.begin():
        policy = session.get(AgencyCallPolicy, DEVELOPMENT_CALL_POLICY_ID)
        if policy is None:
            policy = session.scalar(
                select(AgencyCallPolicy).where(
                    AgencyCallPolicy.agency_id == DEVELOPMENT_AGENCY_ID
                )
            )
        policy_changed = policy is None or any(
            getattr(policy, key) != value for key, value in policy_values.items()
        )
        if policy is None:
            session.add(
                AgencyCallPolicy(
                    id=DEVELOPMENT_CALL_POLICY_ID,
                    agency_id=DEVELOPMENT_AGENCY_ID,
                    created_by=DEVELOPMENT_ACTOR_USER_ID,
                    **policy_values,
                )
            )
        elif policy_changed:
            for key, value in policy_values.items():
                setattr(policy, key, value)

        mapped_number = session.scalar(
            select(AgencyInboundNumber).where(
                AgencyInboundNumber.phone_number_e164 == inbound_number
            )
        )
        if (
            mapped_number is not None
            and mapped_number.agency_id != DEVELOPMENT_AGENCY_ID
        ):
            raise ValueError("the demo inbound number belongs to another agency")
        number = session.get(AgencyInboundNumber, DEVELOPMENT_INBOUND_NUMBER_ID)
        if number is None:
            number = mapped_number
        number_values: dict[str, object] = {
            "phone_number_e164": inbound_number,
            "label": "Harborline phone-agent demo",
            "status": InboundNumberStatus.ACTIVE.value,
            "updated_by": DEVELOPMENT_ACTOR_USER_ID,
        }
        number_changed = number is None or any(
            getattr(number, key) != value for key, value in number_values.items()
        )
        if number is None:
            session.add(
                AgencyInboundNumber(
                    id=DEVELOPMENT_INBOUND_NUMBER_ID,
                    agency_id=DEVELOPMENT_AGENCY_ID,
                    created_by=DEVELOPMENT_ACTOR_USER_ID,
                    **number_values,
                )
            )
        elif number_changed:
            for key, value in number_values.items():
                setattr(number, key, value)
        return policy_changed, number_changed


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
