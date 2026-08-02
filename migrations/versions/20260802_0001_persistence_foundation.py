"""Create the first approved persistence tables.

Revision ID: 20260802_0001
Revises:
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260802_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_primary_key() -> sa.Column[object]:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def created_at_column() -> sa.Column[object]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def updated_at_column() -> sa.Column[object]:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def row_version_column() -> sa.Column[object]:
    return sa.Column(
        "row_version",
        sa.BigInteger(),
        nullable=False,
        server_default=sa.text("1"),
    )


def archived_at_column() -> sa.Column[object]:
    return sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "agencies",
        uuid_primary_key(),
        sa.Column("name", sa.String(length=200), nullable=False),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        archived_at_column(),
        sa.CheckConstraint(
            "length(btrim(name)) > 0",
            name="ck_agencies_name_not_blank",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="ck_agencies_row_version_positive",
        ),
    )

    op.create_table(
        "app_users",
        uuid_primary_key(),
        sa.Column("auth_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        archived_at_column(),
        sa.CheckConstraint(
            "length(btrim(auth_subject)) > 0",
            name="ck_app_users_auth_subject_not_blank",
        ),
        sa.CheckConstraint(
            "email IS NULL OR length(btrim(email)) > 0",
            name="ck_app_users_email_not_blank",
        ),
        sa.CheckConstraint(
            "display_name IS NULL OR length(btrim(display_name)) > 0",
            name="ck_app_users_display_name_not_blank",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="ck_app_users_row_version_positive",
        ),
        sa.UniqueConstraint(
            "auth_subject",
            name="uq_app_users_auth_subject",
        ),
    )

    op.create_table(
        "agency_memberships",
        uuid_primary_key(),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "app_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_agency_memberships_status_valid",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="ck_agency_memberships_row_version_positive",
        ),
        sa.UniqueConstraint(
            "agency_id",
            "app_user_id",
            name="uq_agency_memberships_agency_user",
        ),
    )
    op.create_index(
        "ix_agency_memberships_user_status",
        "agency_memberships",
        ["app_user_id", "status"],
    )

    op.create_table(
        "customers",
        uuid_primary_key(),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("address_city", sa.String(length=100), nullable=True),
        sa.Column("address_state_code", sa.String(length=2), nullable=True),
        sa.Column("address_postal_code", sa.String(length=20), nullable=True),
        sa.Column(
            "search_text",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        archived_at_column(),
        sa.CheckConstraint(
            "length(btrim(full_name)) > 0",
            name="ck_customers_full_name_not_blank",
        ),
        sa.CheckConstraint(
            "email IS NULL OR length(btrim(email)) > 0",
            name="ck_customers_email_not_blank",
        ),
        sa.CheckConstraint(
            "phone IS NULL OR length(btrim(phone)) > 0",
            name="ck_customers_phone_not_blank",
        ),
        sa.CheckConstraint(
            "address_state_code IS NULL OR address_state_code ~ '^[A-Z]{2}$'",
            name="ck_customers_state_code_valid",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="ck_customers_row_version_positive",
        ),
    )
    op.create_index(
        "ix_customers_agency_archive_updated",
        "customers",
        ["agency_id", "archived_at", sa.text("updated_at DESC"), "id"],
    )
    op.create_index(
        "ix_customers_search_text_trgm",
        "customers",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )

    op.create_table(
        "audit_events",
        uuid_primary_key(),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "correlation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "event_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        created_at_column(),
        sa.CheckConstraint(
            "length(btrim(actor_type)) > 0",
            name="ck_audit_events_actor_type_not_blank",
        ),
        sa.CheckConstraint(
            "length(btrim(event_type)) > 0",
            name="ck_audit_events_event_type_not_blank",
        ),
        sa.CheckConstraint(
            "length(btrim(target_type)) > 0",
            name="ck_audit_events_target_type_not_blank",
        ),
        sa.CheckConstraint(
            "length(btrim(summary)) > 0",
            name="ck_audit_events_summary_not_blank",
        ),
        sa.CheckConstraint(
            "event_version > 0",
            name="ck_audit_events_event_version_positive",
        ),
    )
    op.create_index(
        "ix_audit_events_agency_created",
        "audit_events",
        ["agency_id", sa.text("created_at DESC"), "id"],
    )
    op.create_index(
        "ix_audit_events_target_created",
        "audit_events",
        ["target_type", "target_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_events_correlation",
        "audit_events",
        ["correlation_id"],
    )

    op.create_table(
        "idempotency_records",
        uuid_primary_key(),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("environment_kind", sa.String(length=30), nullable=False),
        sa.Column("actor_identifier", sa.String(length=255), nullable=False),
        sa.Column("route_key", sa.String(length=200), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'IN_PROGRESS'"),
        ),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column(
            "response_body",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        sa.CheckConstraint(
            "length(btrim(environment_kind)) > 0",
            name="ck_idempotency_records_environment_not_blank",
        ),
        sa.CheckConstraint(
            "length(btrim(actor_identifier)) > 0",
            name="ck_idempotency_records_actor_identifier_not_blank",
        ),
        sa.CheckConstraint(
            "length(btrim(route_key)) > 0",
            name="ck_idempotency_records_route_key_not_blank",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 128",
            name="ck_idempotency_records_key_length_valid",
        ),
        sa.CheckConstraint(
            "length(request_hash) = 64",
            name="ck_idempotency_records_request_hash_valid",
        ),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="ck_idempotency_records_status_valid",
        ),
        sa.CheckConstraint(
            "response_status_code IS NULL OR response_status_code BETWEEN 100 AND 599",
            name="ck_idempotency_records_response_status_valid",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="ck_idempotency_records_row_version_positive",
        ),
        sa.UniqueConstraint(
            "agency_id",
            "environment_kind",
            "actor_identifier",
            "route_key",
            "idempotency_key",
            name="uq_idempotency_records_scope",
        ),
    )
    op.create_index(
        "ix_idempotency_records_expiry",
        "idempotency_records",
        ["expires_at", "status"],
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("audit_events")
    op.drop_table("customers")
    op.drop_table("agency_memberships")
    op.drop_table("app_users")
    op.drop_table("agencies")
