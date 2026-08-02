from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from insurance_operations.database.models import Base, TABLE_OWNERSHIP


EXPECTED_OWNERSHIP = {
    "agencies": ("identity", None),
    "app_users": ("identity", None),
    "agency_memberships": ("identity", "agency_id"),
    "customers": ("customers", "agency_id"),
    "audit_events": ("audit", "agency_id"),
    "idempotency_records": ("idempotency", "agency_id"),
}


def test_every_foundation_table_has_explicit_ownership() -> None:
    assert set(TABLE_OWNERSHIP) == set(Base.metadata.tables)
    assert {
        table_name: (ownership.module, ownership.agency_column)
        for table_name, ownership in TABLE_OWNERSHIP.items()
    } == EXPECTED_OWNERSHIP


def test_agency_owned_tables_use_restrictive_foreign_keys(
    migrated_database: Engine,
) -> None:
    database_inspector = inspect(migrated_database)

    for table_name, ownership in TABLE_OWNERSHIP.items():
        if ownership.agency_column is None:
            continue

        agency_foreign_keys = [
            foreign_key
            for foreign_key in database_inspector.get_foreign_keys(table_name)
            if foreign_key["constrained_columns"] == [ownership.agency_column]
            and foreign_key["referred_table"] == "agencies"
        ]

        assert len(agency_foreign_keys) == 1
        assert agency_foreign_keys[0]["options"]["ondelete"] == "RESTRICT"
