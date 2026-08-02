from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from insurance_operations.database.models import Agency, AgencyMembership, AppUser
from insurance_operations.database.seed import (
    DEVELOPMENT_AGENCY_ID,
    seed_development_agency,
)
from insurance_operations.settings import (
    DatabaseSettings,
    DatabaseSslMode,
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


def test_migration_creates_only_the_approved_foundation_tables(
    migrated_database: Engine,
) -> None:
    table_names = set(inspect(migrated_database).get_table_names())

    assert EXPECTED_TABLES <= table_names
    assert table_names <= EXPECTED_TABLES | {"alembic_version"}


def test_migration_creates_customer_and_audit_indexes(
    migrated_database: Engine,
) -> None:
    database_inspector = inspect(migrated_database)
    customer_indexes = {
        index["name"] for index in database_inspector.get_indexes("customers")
    }
    audit_indexes = {
        index["name"] for index in database_inspector.get_indexes("audit_events")
    }

    assert {
        "ix_customers_agency_archive_updated",
        "ix_customers_search_text_trgm",
    } <= customer_indexes
    assert {
        "ix_audit_events_agency_created",
        "ix_audit_events_target_created",
        "ix_audit_events_correlation",
    } <= audit_indexes


def test_row_version_and_membership_constraints_are_enforced(
    migrated_database: Engine,
) -> None:
    agency_id = uuid4()
    user_id = uuid4()
    with migrated_database.begin() as connection:
        connection.execute(
            Agency.__table__.insert().values(id=agency_id, name="Constraint Agency")
        )
        connection.execute(
            AppUser.__table__.insert().values(
                id=user_id,
                auth_subject=f"test-{user_id}",
            )
        )

    with pytest.raises(IntegrityError):
        with migrated_database.begin() as connection:
            connection.execute(
                Agency.__table__.insert().values(
                    id=uuid4(),
                    name="Invalid Version",
                    row_version=0,
                )
            )

    with pytest.raises(IntegrityError):
        with migrated_database.begin() as connection:
            connection.execute(
                AgencyMembership.__table__.insert().values(
                    agency_id=agency_id,
                    app_user_id=user_id,
                    status="UNKNOWN",
                )
            )


def test_development_seed_is_idempotent(migrated_database: Engine) -> None:
    settings = DatabaseSettings(
        app_environment=RuntimeEnvironment.DEVELOPMENT,
        database_url=migrated_database.url.render_as_string(hide_password=False),
        database_ssl_mode=DatabaseSslMode.DISABLE,
    )

    assert seed_development_agency(settings) is True
    assert seed_development_agency(settings) is False

    with migrated_database.connect() as connection:
        agency_count = connection.scalar(
            select(func.count())
            .select_from(Agency)
            .where(Agency.id == DEVELOPMENT_AGENCY_ID)
        )

    assert agency_count == 1


def test_development_seed_refuses_non_development_environments(
    database_settings: DatabaseSettings,
) -> None:
    with pytest.raises(ValueError, match="APP_ENVIRONMENT=development"):
        seed_development_agency(database_settings)
