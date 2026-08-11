from uuid import uuid4

import pytest
from sqlalchemy import func, insert, inspect, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from insurance_operations.database.models import (
    Agency,
    AgencyApprovedFaq,
    AgencyMembership,
    AgencyReceptionistSettings,
    AppUser,
)
from insurance_operations.database.seed import (
    DEVELOPMENT_ACTOR_USER_ID,
    DEVELOPMENT_AGENCY_ID,
    DEVELOPMENT_AGENCY_SLUG,
    DEVELOPMENT_APPROVED_FAQ_IDS,
    DEVELOPMENT_MEMBERSHIP_ID,
    DEVELOPMENT_RECEPTIONIST_SETTINGS_ID,
    seed_development_foundation,
)
from insurance_operations.settings import (
    DatabaseSettings,
    RuntimeEnvironment,
)

EXPECTED_TABLES = {
    "agencies",
    "app_users",
    "agency_memberships",
    "customers",
    "audit_events",
    "idempotency_records",
    "conversation_sessions",
    "conversation_intakes",
    "agency_receptionist_settings",
    "agency_approved_faqs",
    "agency_leads",
    "lead_handoff_requests",
    "agency_call_policies",
    "agency_inbound_numbers",
    "inbound_calls",
    "inbound_call_events",
}

EXPECTED_COLUMNS = {
    "agencies": {
        "id",
        "name",
        "slug",
        "environment_kind",
        "created_at",
        "updated_at",
        "row_version",
        "archived_at",
    },
    "app_users": {
        "id",
        "auth_subject",
        "display_name",
        "email_snapshot",
        "status",
        "created_at",
        "updated_at",
        "row_version",
        "disabled_at",
    },
    "agency_memberships": {
        "id",
        "agency_id",
        "app_user_id",
        "status",
        "created_at",
        "updated_at",
        "row_version",
        "deactivated_at",
    },
    "customers": {
        "id",
        "agency_id",
        "demo_session_id",
        "full_name",
        "normalized_name",
        "email",
        "normalized_email",
        "phone",
        "normalized_phone",
        "address_line1",
        "address_line2",
        "city",
        "state_code",
        "postal_code",
        "country_code",
        "search_text",
        "created_by",
        "created_at",
        "updated_at",
        "row_version",
        "archived_at",
    },
    "audit_events": {
        "id",
        "agency_id",
        "demo_session_id",
        "actor_type",
        "actor_user_id",
        "event_type",
        "occurred_at",
        "customer_id",
        "document_id",
        "attempt_id",
        "review_id",
        "policy_version_id",
        "email_delivery_id",
        "summary",
        "details",
        "correlation_id",
        "event_version",
        "created_at",
    },
    "idempotency_records": {
        "id",
        "agency_id",
        "demo_session_id",
        "actor_scope_type",
        "actor_scope_id",
        "route_key",
        "idempotency_key",
        "request_fingerprint",
        "status",
        "response_status",
        "response_body",
        "resource_type",
        "resource_id",
        "failure_code",
        "created_at",
        "completed_at",
        "expires_at",
    },
    "conversation_sessions": {
        "id",
        "agency_id",
        "initiated_by",
        "status",
        "provider_metadata",
        "disclosure_accepted_at",
        "microphone_consent_at",
        "synthetic_data_acknowledged_at",
        "maximum_duration_seconds",
        "authorization_expires_at",
        "confirmation_expires_at",
        "authorized_at",
        "ended_at",
        "confirmed_at",
        "failure_code",
        "created_at",
        "updated_at",
        "row_version",
    },
    "conversation_intakes": {
        "id",
        "agency_id",
        "customer_id",
        "conversation_session_id",
        "created_by",
        "confirmation_source",
        "intake_intent",
        "confirmed_transcript",
        "confirmed_at",
        "created_at",
    },
    "agency_receptionist_settings": {
        "id",
        "agency_id",
        "public_name",
        "greeting",
        "office_hours",
        "contact_email",
        "contact_phone",
        "supported_insurance_categories",
        "escalation_message",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "row_version",
    },
    "agency_approved_faqs": {
        "id",
        "agency_id",
        "question",
        "normalized_question",
        "approved_answer",
        "status",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "row_version",
    },
    "agency_leads": {
        "id",
        "agency_id",
        "customer_id",
        "conversation_intake_id",
        "status",
        "urgency",
        "summary",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "row_version",
    },
    "lead_handoff_requests": {
        "id",
        "agency_id",
        "lead_id",
        "conversation_session_id",
        "inbound_call_id",
        "request_kind",
        "preferred_contact_method",
        "reason",
        "availability",
        "transfer_attempted",
        "status",
        "created_by",
        "updated_by",
        "completed_at",
        "cancelled_at",
        "created_at",
        "updated_at",
        "row_version",
    },
    "agency_call_policies": {
        "id",
        "agency_id",
        "inbound_enabled",
        "timezone",
        "availability_windows",
        "transfer_enabled",
        "transfer_destination_e164",
        "transfer_ring_timeout_seconds",
        "max_concurrent_calls",
        "daily_call_limit",
        "callback_fallback_enabled",
        "after_hours_message",
        "unavailable_message",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "row_version",
    },
    "agency_inbound_numbers": {
        "id",
        "agency_id",
        "phone_number_e164",
        "label",
        "status",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "row_version",
    },
    "inbound_calls": {
        "id",
        "agency_id",
        "inbound_number_id",
        "lead_id",
        "status",
        "caller_number_e164",
        "adapter_name",
        "source_call_reference",
        "adapter_metadata",
        "policy_snapshot",
        "received_at",
        "answered_at",
        "ended_at",
        "failure_code",
        "created_at",
        "updated_at",
        "row_version",
    },
    "inbound_call_events": {
        "id",
        "agency_id",
        "inbound_call_id",
        "event_key",
        "event_type",
        "occurred_at",
        "details",
        "created_at",
    },
}


def test_migration_creates_only_the_approved_foundation_tables(
    migrated_database: Engine,
) -> None:
    table_names = set(inspect(migrated_database).get_table_names())

    assert table_names >= EXPECTED_TABLES
    assert table_names <= EXPECTED_TABLES | {"alembic_version"}


def test_migration_columns_match_the_approved_contract(
    migrated_database: Engine,
) -> None:
    database_inspector = inspect(migrated_database)

    actual_columns = {
        table_name: {
            column["name"] for column in database_inspector.get_columns(table_name)
        }
        for table_name in EXPECTED_TABLES
    }

    assert actual_columns == EXPECTED_COLUMNS


def test_migration_creates_only_the_documented_foundation_indexes(
    migrated_database: Engine,
) -> None:
    database_inspector = inspect(migrated_database)
    agency_indexes = {
        index["name"] for index in database_inspector.get_indexes("agencies")
    }
    customer_indexes = {
        index["name"] for index in database_inspector.get_indexes("customers")
    }
    audit_indexes = {
        index["name"] for index in database_inspector.get_indexes("audit_events")
    }
    conversation_session_indexes = {
        index["name"]
        for index in database_inspector.get_indexes("conversation_sessions")
    }
    conversation_intake_indexes = {
        index["name"]
        for index in database_inspector.get_indexes("conversation_intakes")
    }
    receptionist_settings_indexes = {
        index["name"]
        for index in database_inspector.get_indexes("agency_receptionist_settings")
    }
    approved_faq_indexes = {
        index["name"]
        for index in database_inspector.get_indexes("agency_approved_faqs")
    }
    lead_indexes = {
        index["name"] for index in database_inspector.get_indexes("agency_leads")
    }
    handoff_indexes = {
        index["name"]
        for index in database_inspector.get_indexes("lead_handoff_requests")
    }
    call_policy_indexes = {
        index["name"]
        for index in database_inspector.get_indexes("agency_call_policies")
    }
    inbound_number_indexes = {
        index["name"]
        for index in database_inspector.get_indexes("agency_inbound_numbers")
    }
    inbound_call_indexes = {
        index["name"] for index in database_inspector.get_indexes("inbound_calls")
    }
    inbound_call_event_indexes = {
        index["name"] for index in database_inspector.get_indexes("inbound_call_events")
    }

    assert agency_indexes == {
        "ix_agencies_environment_kind",
        "uq_agencies_slug",
    }
    assert customer_indexes == {
        "ix_customers_agency_archive_updated",
        "ix_customers_search_text_trgm",
    }
    assert audit_indexes == {
        "ix_audit_events_customer_occurred",
        "ix_audit_events_document_occurred",
        "ix_audit_events_policy_version_occurred",
    }
    assert conversation_session_indexes == {
        "ix_conversation_sessions_agency_authorized",
        "ix_conversation_sessions_agency_created",
        "ix_conversation_sessions_agency_status_expires",
    }
    assert conversation_intake_indexes == {
        "ix_conversation_intakes_customer_confirmed",
        "uq_conversation_intakes_session",
    }
    assert receptionist_settings_indexes == {"uq_agency_receptionist_settings_agency"}
    assert approved_faq_indexes == {
        "ix_agency_approved_faqs_agency_status",
        "uq_agency_approved_faqs_agency_question",
    }
    assert lead_indexes == {
        "ix_agency_leads_agency_status_created",
        "ix_agency_leads_customer_created",
        "uq_agency_leads_conversation_intake",
    }
    assert handoff_indexes == {
        "ix_handoff_requests_agency_status",
        "ix_handoff_requests_lead_created",
        "uq_handoff_requests_inbound_call",
    }
    assert call_policy_indexes == {"uq_agency_call_policies_agency"}
    assert inbound_number_indexes == {
        "ix_inbound_numbers_agency_status",
        "uq_agency_inbound_numbers_phone",
    }
    assert inbound_call_indexes == {
        "ix_inbound_calls_agency_status_created",
        "ix_inbound_calls_number_created",
        "uq_inbound_calls_adapter_reference",
    }
    assert inbound_call_event_indexes == {
        "ix_inbound_call_events_call_occurred",
        "uq_inbound_call_events_call_key",
    }


def test_migration_unique_constraints_match_the_approved_scopes(
    migrated_database: Engine,
) -> None:
    database_inspector = inspect(migrated_database)
    expected_unique_columns: dict[str, set[tuple[str, ...]]] = {
        "agencies": {("slug",)},
        "app_users": {("auth_subject",)},
        "agency_memberships": {("agency_id", "app_user_id")},
        "customers": set(),
        "audit_events": set(),
        "idempotency_records": {
            (
                "actor_scope_type",
                "actor_scope_id",
                "route_key",
                "idempotency_key",
            )
        },
        "conversation_sessions": set(),
        "conversation_intakes": {("conversation_session_id",)},
        "agency_receptionist_settings": {("agency_id",)},
        "agency_approved_faqs": {("agency_id", "normalized_question")},
        "agency_leads": {("conversation_intake_id",)},
        "lead_handoff_requests": {("inbound_call_id",)},
        "agency_call_policies": {("agency_id",)},
        "agency_inbound_numbers": {("phone_number_e164",)},
        "inbound_calls": {("adapter_name", "source_call_reference")},
        "inbound_call_events": {("inbound_call_id", "event_key")},
    }
    actual_unique_columns = {
        table_name: {
            tuple(constraint["column_names"])
            for constraint in database_inspector.get_unique_constraints(table_name)
        }
        for table_name in expected_unique_columns
    }

    assert actual_unique_columns == expected_unique_columns


def test_migration_check_constraints_cover_approved_invariants(
    migrated_database: Engine,
) -> None:
    database_inspector = inspect(migrated_database)
    expected_constraint_names = {
        "agencies": {
            "ck_agencies_name_length_valid",
            "ck_agencies_slug_lowercase",
            "ck_agencies_environment_kind_valid",
            "ck_agencies_row_version_positive",
        },
        "app_users": {
            "ck_app_users_display_name_length_valid",
            "ck_app_users_status_valid",
            "ck_app_users_disabled_at_consistent",
            "ck_app_users_row_version_positive",
        },
        "agency_memberships": {
            "ck_agency_memberships_status_valid",
            "ck_agency_memberships_row_version_positive",
        },
        "customers": {
            "ck_customers_full_name_length_valid",
            "ck_customers_state_code_length_valid",
            "ck_customers_country_code_length_valid",
            "ck_customers_row_version_positive",
        },
        "audit_events": {
            "ck_audit_events_actor_type_valid",
            "ck_audit_events_event_version_positive",
        },
        "idempotency_records": {
            "ck_idempotency_records_key_length_valid",
            "ck_idempotency_records_status_valid",
        },
        "conversation_sessions": {
            "ck_conversation_sessions_status_valid",
            "ck_conversation_sessions_duration_valid",
            "ck_conversation_sessions_provider_metadata_object",
            "ck_conversation_sessions_confirmed_at_consistent",
            "ck_conversation_sessions_row_version_positive",
        },
        "conversation_intakes": {
            "ck_conversation_intakes_confirmation_source_valid",
            "ck_conversation_intakes_intake_intent_length_valid",
            "ck_conversation_intakes_transcript_array_valid",
        },
        "agency_receptionist_settings": {
            "ck_agency_receptionist_settings_public_name_length_valid",
            "ck_agency_receptionist_settings_greeting_length_valid",
            "ck_agency_receptionist_settings_office_hours_length_valid",
            "ck_agency_receptionist_settings_contact_email_length_valid",
            "ck_agency_receptionist_settings_contact_phone_length_valid",
            "ck_agency_receptionist_settings_contact_method_required",
            "ck_agency_receptionist_settings_supported_categories_valid",
            "ck_agency_receptionist_settings_escalation_message_length_valid",
            "ck_agency_receptionist_settings_row_version_positive",
        },
        "agency_approved_faqs": {
            "ck_agency_approved_faqs_question_length_valid",
            "ck_agency_approved_faqs_normalized_question_valid",
            "ck_agency_approved_faqs_answer_length_valid",
            "ck_agency_approved_faqs_status_valid",
            "ck_agency_approved_faqs_row_version_positive",
        },
        "agency_leads": {
            "ck_agency_leads_status_valid",
            "ck_agency_leads_urgency_valid",
            "ck_agency_leads_summary_length_valid",
            "ck_agency_leads_row_version_positive",
        },
        "lead_handoff_requests": {
            "ck_lead_handoff_requests_request_kind_valid",
            "ck_lead_handoff_requests_contact_method_valid",
            "ck_lead_handoff_requests_reason_length_valid",
            "ck_lead_handoff_requests_availability_length_valid",
            "ck_lead_handoff_requests_status_valid",
            "ck_lead_handoff_requests_completed_at_consistent",
            "ck_lead_handoff_requests_cancelled_at_consistent",
            "ck_lead_handoff_requests_row_version_positive",
        },
        "agency_call_policies": {
            "ck_agency_call_policies_timezone_length_valid",
            "ck_agency_call_policies_transfer_number_length_valid",
            "ck_agency_call_policies_transfer_destination_required",
            "ck_agency_call_policies_ring_timeout_valid",
            "ck_agency_call_policies_concurrent_limit_valid",
            "ck_agency_call_policies_daily_limit_valid",
            "ck_agency_call_policies_availability_windows_array",
            "ck_agency_call_policies_after_hours_message_valid",
            "ck_agency_call_policies_unavailable_message_valid",
            "ck_agency_call_policies_row_version_positive",
        },
        "agency_inbound_numbers": {
            "ck_agency_inbound_numbers_phone_number_length_valid",
            "ck_agency_inbound_numbers_label_length_valid",
            "ck_agency_inbound_numbers_status_valid",
            "ck_agency_inbound_numbers_row_version_positive",
        },
        "inbound_calls": {
            "ck_inbound_calls_status_valid",
            "ck_inbound_calls_caller_number_length_valid",
            "ck_inbound_calls_adapter_name_length_valid",
            "ck_inbound_calls_source_reference_length_valid",
            "ck_inbound_calls_failure_code_length_valid",
            "ck_inbound_calls_answered_time_valid",
            "ck_inbound_calls_ended_time_valid",
            "ck_inbound_calls_failure_code_consistent",
            "ck_inbound_calls_adapter_metadata_object",
            "ck_inbound_calls_policy_snapshot_object",
            "ck_inbound_calls_row_version_positive",
        },
        "inbound_call_events": {
            "ck_inbound_call_events_event_type_length_valid",
            "ck_inbound_call_events_event_key_length_valid",
            "ck_inbound_call_events_details_object",
        },
    }
    actual_constraint_names = {
        table_name: {
            constraint["name"]
            for constraint in database_inspector.get_check_constraints(table_name)
        }
        for table_name in expected_constraint_names
    }

    assert actual_constraint_names == expected_constraint_names


def test_row_version_and_membership_constraints_are_enforced(
    migrated_database: Engine,
) -> None:
    agency_id = uuid4()
    user_id = uuid4()
    with migrated_database.begin() as connection:
        connection.execute(
            insert(Agency).values(
                id=agency_id,
                name="Constraint Agency",
                slug=f"constraint-{agency_id}",
                environment_kind="DEVELOPMENT",
            )
        )
        connection.execute(
            insert(AppUser).values(
                id=user_id,
                auth_subject=uuid4(),
                display_name="Constraint User",
            )
        )

    with pytest.raises(IntegrityError), migrated_database.begin() as connection:
        connection.execute(
            insert(Agency).values(
                id=uuid4(),
                name="Invalid Version",
                slug=f"invalid-{uuid4()}",
                environment_kind="DEVELOPMENT",
                row_version=0,
            )
        )

    with pytest.raises(IntegrityError), migrated_database.begin() as connection:
        connection.execute(
            insert(AgencyMembership).values(
                agency_id=agency_id,
                app_user_id=user_id,
                status="UNKNOWN",
            )
        )


def test_mutable_records_increment_row_version_on_update(
    migrated_database: Engine,
) -> None:
    agency_id = uuid4()
    with migrated_database.begin() as connection:
        connection.execute(
            insert(Agency).values(
                id=agency_id,
                name="Versioned Agency",
                slug=f"versioned-{agency_id}",
                environment_kind="DEVELOPMENT",
            )
        )
        connection.execute(
            update(Agency).where(Agency.id == agency_id).values(name="Updated Agency")
        )
        row_version = connection.scalar(
            select(Agency.row_version).where(Agency.id == agency_id)
        )

    assert row_version == 2


def test_development_seed_is_idempotent(
    migrated_database: Engine,
    database_settings: DatabaseSettings,
) -> None:
    settings = DatabaseSettings.model_validate(
        {
            "app_environment": RuntimeEnvironment.DEVELOPMENT,
            "database_url": database_settings.runtime_database_url,
            "direct_database_url": None,
            "test_database_url": None,
            "database_ssl_mode": database_settings.database_ssl_mode,
            "database_pool_size": database_settings.database_pool_size,
            "database_max_overflow": database_settings.database_max_overflow,
            "database_pool_timeout_seconds": (
                database_settings.database_pool_timeout_seconds
            ),
            "database_pool_recycle_seconds": (
                database_settings.database_pool_recycle_seconds
            ),
        }
    )

    assert settings.database_ssl_mode is database_settings.database_ssl_mode

    first_result = seed_development_foundation(settings)
    second_result = seed_development_foundation(settings)

    assert first_result.agency_created is True
    assert first_result.actor_created is True
    assert first_result.membership_created is True
    assert first_result.receptionist_settings_created is True
    assert first_result.approved_faqs_created == 3
    assert second_result.agency_created is False
    assert second_result.actor_created is False
    assert second_result.membership_created is False
    assert second_result.receptionist_settings_created is False
    assert second_result.approved_faqs_created == 0

    with Session(migrated_database) as session:
        receptionist_settings = session.get(
            AgencyReceptionistSettings,
            DEVELOPMENT_RECEPTIONIST_SETTINGS_ID,
        )
        approved_faq_count = session.scalar(
            select(func.count())
            .select_from(AgencyApprovedFaq)
            .where(AgencyApprovedFaq.id.in_(DEVELOPMENT_APPROVED_FAQ_IDS))
        )

    assert receptionist_settings is not None
    assert approved_faq_count == 3

    with migrated_database.connect() as connection:
        seeded_agency = connection.execute(
            select(Agency.slug, Agency.environment_kind).where(
                Agency.id == DEVELOPMENT_AGENCY_ID
            )
        ).one()
        agency_count = connection.scalar(
            select(func.count())
            .select_from(Agency)
            .where(Agency.id == DEVELOPMENT_AGENCY_ID)
        )
        actor_count = connection.scalar(
            select(func.count())
            .select_from(AppUser)
            .where(AppUser.id == DEVELOPMENT_ACTOR_USER_ID)
        )
        membership_count = connection.scalar(
            select(func.count())
            .select_from(AgencyMembership)
            .where(AgencyMembership.id == DEVELOPMENT_MEMBERSHIP_ID)
        )

    assert agency_count == 1
    assert actor_count == 1
    assert membership_count == 1
    assert seeded_agency.slug == DEVELOPMENT_AGENCY_SLUG
    assert seeded_agency.environment_kind == "DEVELOPMENT"


@pytest.mark.parametrize(
    "environment",
    [RuntimeEnvironment.TEST, RuntimeEnvironment.PRODUCTION],
)
def test_development_seed_refuses_non_development_environments(
    database_settings: DatabaseSettings,
    environment: RuntimeEnvironment,
) -> None:
    settings = database_settings.model_copy(
        update={"app_environment": environment},
    )

    with pytest.raises(ValueError, match="APP_ENVIRONMENT=development"):
        seed_development_foundation(settings)
