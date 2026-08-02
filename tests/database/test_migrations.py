from uuid import uuid4

import pytest
from sqlalchemy import func, insert, inspect, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from insurance_operations.database.models import Agency, AgencyMembership, AppUser
from insurance_operations.database.seed import (
    DEVELOPMENT_AGENCY_ID,
    DEVELOPMENT_AGENCY_SLUG,
    seed_development_agency,
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

    assert seed_development_agency(settings) is True
    assert seed_development_agency(settings) is False

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

    assert agency_count == 1
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
        seed_development_agency(settings)
