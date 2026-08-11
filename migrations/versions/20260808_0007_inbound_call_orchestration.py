"""Create inbound call orchestration.

Revision ID: 20260808_0007
Revises: 20260808_0006
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0007"
down_revision: str | None = "20260808_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agency_call_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("inbound_enabled", sa.Boolean(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column(
            "availability_windows",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("transfer_enabled", sa.Boolean(), nullable=False),
        sa.Column("transfer_destination_e164", sa.Text(), nullable=True),
        sa.Column(
            "transfer_ring_timeout_seconds",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("max_concurrent_calls", sa.Integer(), nullable=False),
        sa.Column("daily_call_limit", sa.Integer(), nullable=False),
        sa.Column("callback_fallback_enabled", sa.Boolean(), nullable=False),
        sa.Column("after_hours_message", sa.Text(), nullable=False),
        sa.Column("unavailable_message", sa.Text(), nullable=False),
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "row_version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.CheckConstraint(
            "length(btrim(timezone)) BETWEEN 1 AND 100",
            name="timezone_length_valid",
        ),
        sa.CheckConstraint(
            "transfer_destination_e164 IS NULL OR "
            "length(transfer_destination_e164) BETWEEN 8 AND 16",
            name="transfer_number_length_valid",
        ),
        sa.CheckConstraint(
            "transfer_enabled = false OR transfer_destination_e164 IS NOT NULL",
            name="transfer_destination_required",
        ),
        sa.CheckConstraint(
            "transfer_ring_timeout_seconds BETWEEN 10 AND 60",
            name="ring_timeout_valid",
        ),
        sa.CheckConstraint(
            "max_concurrent_calls BETWEEN 1 AND 20",
            name="concurrent_limit_valid",
        ),
        sa.CheckConstraint(
            "daily_call_limit BETWEEN 1 AND 1000",
            name="daily_limit_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(availability_windows) = 'array'",
            name="availability_windows_array",
        ),
        sa.CheckConstraint(
            "length(btrim(after_hours_message)) BETWEEN 1 AND 600",
            name="after_hours_message_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(unavailable_message)) BETWEEN 1 AND 600",
            name="unavailable_message_valid",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.UniqueConstraint("agency_id", name="uq_agency_call_policies_agency"),
    )
    op.execute(
        """
        CREATE TRIGGER trg_agency_call_policies_mutable_metadata
        BEFORE UPDATE ON agency_call_policies
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )

    op.create_table(
        "agency_inbound_numbers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("phone_number_e164", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="INACTIVE",
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "row_version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.CheckConstraint(
            "length(phone_number_e164) BETWEEN 8 AND 16",
            name="phone_number_length_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(label)) BETWEEN 1 AND 120",
            name="label_length_valid",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_valid",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.UniqueConstraint(
            "phone_number_e164",
            name="uq_agency_inbound_numbers_phone",
        ),
    )
    op.create_index(
        "ix_inbound_numbers_agency_status",
        "agency_inbound_numbers",
        ["agency_id", "status"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_agency_inbound_numbers_mutable_metadata
        BEFORE UPDATE ON agency_inbound_numbers
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )

    op.create_table(
        "inbound_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inbound_number_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agency_inbound_numbers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agency_leads.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="RECEIVED",
        ),
        sa.Column("caller_number_e164", sa.Text(), nullable=True),
        sa.Column("adapter_name", sa.Text(), nullable=False),
        sa.Column("source_call_reference", sa.Text(), nullable=False),
        sa.Column(
            "adapter_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "policy_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "row_version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'CONNECTED', 'TRANSFER_PENDING', "
            "'TRANSFERRED', 'CALLBACK_PENDING', 'CALLBACK_REQUESTED', "
            "'COMPLETED', 'FAILED')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "caller_number_e164 IS NULL OR length(caller_number_e164) BETWEEN 8 AND 16",
            name="caller_number_length_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(adapter_name)) BETWEEN 1 AND 80",
            name="adapter_name_length_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(source_call_reference)) BETWEEN 1 AND 200",
            name="source_reference_length_valid",
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR length(failure_code) BETWEEN 1 AND 80",
            name="failure_code_length_valid",
        ),
        sa.CheckConstraint(
            "answered_at IS NULL OR answered_at >= received_at",
            name="answered_time_valid",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= received_at",
            name="ended_time_valid",
        ),
        sa.CheckConstraint(
            "(status = 'FAILED' AND failure_code IS NOT NULL) OR "
            "(status <> 'FAILED' AND failure_code IS NULL)",
            name="failure_code_consistent",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(adapter_metadata) = 'object'",
            name="adapter_metadata_object",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(policy_snapshot) = 'object'",
            name="policy_snapshot_object",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.UniqueConstraint(
            "adapter_name",
            "source_call_reference",
            name="uq_inbound_calls_adapter_reference",
        ),
    )
    op.create_index(
        "ix_inbound_calls_agency_status_created",
        "inbound_calls",
        ["agency_id", "status", "created_at"],
    )
    op.create_index(
        "ix_inbound_calls_number_created",
        "inbound_calls",
        ["inbound_number_id", "created_at"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_inbound_calls_mutable_metadata
        BEFORE UPDATE ON inbound_calls
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )

    op.add_column(
        "lead_handoff_requests",
        sa.Column("inbound_call_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_handoff_requests_inbound_call",
        "lead_handoff_requests",
        "inbound_calls",
        ["inbound_call_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_handoff_requests_inbound_call",
        "lead_handoff_requests",
        ["inbound_call_id"],
    )

    op.create_table(
        "inbound_call_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inbound_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inbound_calls.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_key", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(btrim(event_type)) BETWEEN 1 AND 80",
            name="event_type_length_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(event_key)) BETWEEN 1 AND 200",
            name="event_key_length_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(details) = 'object'",
            name="details_object",
        ),
        sa.UniqueConstraint(
            "inbound_call_id",
            "event_key",
            name="uq_inbound_call_events_call_key",
        ),
    )
    op.create_index(
        "ix_inbound_call_events_call_occurred",
        "inbound_call_events",
        ["inbound_call_id", "occurred_at"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_inbound_call_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'inbound call events are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_inbound_call_events_immutable
        BEFORE UPDATE OR DELETE ON inbound_call_events
        FOR EACH ROW EXECUTE FUNCTION reject_inbound_call_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_inbound_call_events_immutable "
        "ON inbound_call_events"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_inbound_call_event_mutation()")
    op.drop_index(
        "ix_inbound_call_events_call_occurred",
        table_name="inbound_call_events",
    )
    op.drop_table("inbound_call_events")

    op.drop_constraint(
        "uq_handoff_requests_inbound_call",
        "lead_handoff_requests",
        type_="unique",
    )
    op.drop_constraint(
        "fk_handoff_requests_inbound_call",
        "lead_handoff_requests",
        type_="foreignkey",
    )
    op.drop_column("lead_handoff_requests", "inbound_call_id")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_inbound_calls_mutable_metadata ON inbound_calls"
    )
    op.drop_index("ix_inbound_calls_number_created", table_name="inbound_calls")
    op.drop_index("ix_inbound_calls_agency_status_created", table_name="inbound_calls")
    op.drop_table("inbound_calls")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_agency_inbound_numbers_mutable_metadata "
        "ON agency_inbound_numbers"
    )
    op.drop_index(
        "ix_inbound_numbers_agency_status",
        table_name="agency_inbound_numbers",
    )
    op.drop_table("agency_inbound_numbers")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_agency_call_policies_mutable_metadata "
        "ON agency_call_policies"
    )
    op.drop_table("agency_call_policies")
