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
    op.execute(
        """
        CREATE FUNCTION set_mutable_record_metadata()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at = clock_timestamp();
            NEW.row_version = OLD.row_version + 1;
            RETURN NEW;
        END;
        $$
        """
    )

    op.create_table(
        "agencies",
        uuid_primary_key(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("environment_kind", sa.Text(), nullable=False),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        archived_at_column(),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 160",
            name="name_length_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(slug)) > 0 AND slug = lower(slug)",
            name="slug_lowercase",
        ),
        sa.CheckConstraint(
            "environment_kind IN ('DEVELOPMENT', 'DEMO', 'PRODUCTION')",
            name="environment_kind_valid",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="row_version_positive",
        ),
        sa.UniqueConstraint("slug", name="uq_agencies_slug"),
    )
    op.create_index(
        "ix_agencies_environment_kind",
        "agencies",
        ["environment_kind"],
    )

    op.create_table(
        "app_users",
        uuid_primary_key(),
        sa.Column("auth_subject", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("email_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(btrim(display_name)) BETWEEN 1 AND 160",
            name="display_name_length_valid",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND disabled_at IS NULL) OR "
            "(status = 'DISABLED' AND disabled_at IS NOT NULL)",
            name="disabled_at_consistent",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="row_version_positive",
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
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="row_version_positive",
        ),
        sa.UniqueConstraint(
            "agency_id",
            "app_user_id",
            name="uq_agency_memberships_agency_user",
        ),
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
        sa.Column("demo_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("normalized_email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("normalized_phone", sa.Text(), nullable=True),
        sa.Column("address_line1", sa.Text(), nullable=True),
        sa.Column("address_line2", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state_code", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.Text(), nullable=True),
        sa.Column(
            "country_code",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'US'"),
        ),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        created_at_column(),
        updated_at_column(),
        row_version_column(),
        archived_at_column(),
        sa.CheckConstraint(
            "length(btrim(full_name)) BETWEEN 1 AND 200",
            name="full_name_length_valid",
        ),
        sa.CheckConstraint(
            "state_code IS NULL OR length(state_code) = 2",
            name="state_code_length_valid",
        ),
        sa.CheckConstraint(
            "length(country_code) = 2",
            name="country_code_length_valid",
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name="row_version_positive",
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
        sa.Column("demo_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email_delivery_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
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
            "actor_type IN ('STAFF', 'DEMO_USER', 'SYSTEM', 'WORKER')",
            name="actor_type_valid",
        ),
        sa.CheckConstraint(
            "event_version > 0",
            name="event_version_positive",
        ),
    )
    op.create_index(
        "ix_audit_events_customer_occurred",
        "audit_events",
        ["customer_id", sa.text("occurred_at DESC"), "id"],
    )
    op.create_index(
        "ix_audit_events_document_occurred",
        "audit_events",
        ["document_id", sa.text("occurred_at DESC"), "id"],
    )
    op.create_index(
        "ix_audit_events_policy_version_occurred",
        "audit_events",
        ["policy_version_id", sa.text("occurred_at DESC"), "id"],
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
        sa.Column("demo_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_scope_type", sa.Text(), nullable=False),
        sa.Column("actor_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_key", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'IN_PROGRESS'"),
        ),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column(
            "response_body",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        created_at_column(),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 128",
            name="key_length_valid",
        ),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="status_valid",
        ),
        sa.UniqueConstraint(
            "actor_scope_type",
            "actor_scope_id",
            "route_key",
            "idempotency_key",
            name="uq_idempotency_records_scope",
        ),
    )

    for table_name in (
        "agencies",
        "app_users",
        "agency_memberships",
        "customers",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_mutable_record_metadata
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION set_mutable_record_metadata()
            """
        )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("audit_events")
    op.drop_table("customers")
    op.drop_table("agency_memberships")
    op.drop_table("app_users")
    op.drop_table("agencies")
    op.execute("DROP FUNCTION set_mutable_record_metadata()")
