"""Create leads and handoff requests.

Revision ID: 20260808_0006
Revises: 20260808_0005
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0006"
down_revision: str | None = "20260808_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agency_leads",
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
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "conversation_intake_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_intakes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="NEW"),
        sa.Column("urgency", sa.Text(), nullable=False, server_default="NORMAL"),
        sa.Column("summary", sa.Text(), nullable=False),
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
            "status IN ('NEW', 'CONTACTED', 'QUALIFIED', 'CLOSED', 'ARCHIVED')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "urgency IN ('LOW', 'NORMAL', 'HIGH')",
            name="urgency_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(summary)) BETWEEN 1 AND 2000",
            name="summary_length_valid",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.UniqueConstraint(
            "conversation_intake_id",
            name="uq_agency_leads_conversation_intake",
        ),
    )
    op.create_index(
        "ix_agency_leads_agency_status_created",
        "agency_leads",
        ["agency_id", "status", "created_at"],
    )
    op.create_index(
        "ix_agency_leads_customer_created",
        "agency_leads",
        ["customer_id", "created_at"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_agency_leads_mutable_metadata
        BEFORE UPDATE ON agency_leads
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )

    op.create_table(
        "lead_handoff_requests",
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
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agency_leads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "conversation_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_sessions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("request_kind", sa.Text(), nullable=False),
        sa.Column("preferred_contact_method", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column(
            "transfer_attempted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="REQUESTED",
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            "request_kind IN ('CALLBACK', 'LIVE_TRANSFER')",
            name="request_kind_valid",
        ),
        sa.CheckConstraint(
            "preferred_contact_method IN ('PHONE', 'EMAIL', 'NO_PREFERENCE')",
            name="contact_method_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 1000",
            name="reason_length_valid",
        ),
        sa.CheckConstraint(
            "availability IS NULL OR length(btrim(availability)) BETWEEN 1 AND 500",
            name="availability_length_valid",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'ACKNOWLEDGED', 'COMPLETED', 'CANCELLED')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
            "(status <> 'COMPLETED' AND completed_at IS NULL)",
            name="completed_at_consistent",
        ),
        sa.CheckConstraint(
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL) OR "
            "(status <> 'CANCELLED' AND cancelled_at IS NULL)",
            name="cancelled_at_consistent",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    op.create_index(
        "ix_handoff_requests_lead_created",
        "lead_handoff_requests",
        ["lead_id", "created_at"],
    )
    op.create_index(
        "ix_handoff_requests_agency_status",
        "lead_handoff_requests",
        ["agency_id", "status", "created_at"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_lead_handoff_requests_mutable_metadata
        BEFORE UPDATE ON lead_handoff_requests
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_lead_handoff_requests_mutable_metadata "
        "ON lead_handoff_requests"
    )
    op.drop_index(
        "ix_handoff_requests_agency_status",
        table_name="lead_handoff_requests",
    )
    op.drop_index(
        "ix_handoff_requests_lead_created",
        table_name="lead_handoff_requests",
    )
    op.drop_table("lead_handoff_requests")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_agency_leads_mutable_metadata ON agency_leads"
    )
    op.drop_index(
        "ix_agency_leads_customer_created",
        table_name="agency_leads",
    )
    op.drop_index(
        "ix_agency_leads_agency_status_created",
        table_name="agency_leads",
    )
    op.drop_table("agency_leads")
