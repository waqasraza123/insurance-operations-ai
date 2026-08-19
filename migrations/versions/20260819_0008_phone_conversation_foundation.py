"""Create the phone conversation confirmation foundation.

Revision ID: 20260819_0008
Revises: 20260808_0007
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260819_0008"
down_revision: str | None = "20260808_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_sessions",
        sa.Column(
            "channel",
            sa.Text(),
            nullable=False,
            server_default="BROWSER",
        ),
    )
    op.add_column(
        "conversation_sessions",
        sa.Column(
            "inbound_call_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_conversation_sessions_inbound_call",
        "conversation_sessions",
        "inbound_calls",
        ["inbound_call_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_conversation_sessions_inbound_call",
        "conversation_sessions",
        ["inbound_call_id"],
    )
    op.create_check_constraint(
        op.f("ck_conversation_sessions_channel_valid"),
        "conversation_sessions",
        "channel IN ('BROWSER', 'PHONE')",
    )
    op.create_check_constraint(
        op.f("ck_conversation_sessions_channel_call_consistent"),
        "conversation_sessions",
        "(channel = 'BROWSER' AND inbound_call_id IS NULL) OR "
        "(channel = 'PHONE' AND inbound_call_id IS NOT NULL)",
    )

    op.create_table(
        "conversation_intake_confirmation_receipts",
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
            "conversation_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inbound_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inbound_calls.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("intake_intent", sa.Text(), nullable=False),
        sa.Column("urgency", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(btrim(full_name)) BETWEEN 1 AND 200",
            name="name_valid",
        ),
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="contact_required",
        ),
        sa.CheckConstraint(
            "length(btrim(intake_intent)) BETWEEN 1 AND 2000",
            name="intent_valid",
        ),
        sa.CheckConstraint(
            "urgency IN ('LOW', 'NORMAL', 'HIGH')",
            name="urgency_valid",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="fingerprint_valid",
        ),
        sa.UniqueConstraint(
            "conversation_session_id",
            name="uq_confirmation_receipts_session",
        ),
        sa.UniqueConstraint(
            "inbound_call_id",
            name="uq_confirmation_receipts_call",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION reject_confirmation_receipt_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'conversation intake confirmation receipts are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_confirmation_receipts_immutable
        BEFORE UPDATE OR DELETE ON conversation_intake_confirmation_receipts
        FOR EACH ROW EXECUTE FUNCTION reject_confirmation_receipt_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_confirmation_receipts_immutable "
        "ON conversation_intake_confirmation_receipts"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_confirmation_receipt_mutation()")
    op.drop_table("conversation_intake_confirmation_receipts")

    op.drop_constraint(
        op.f("ck_conversation_sessions_channel_call_consistent"),
        "conversation_sessions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_conversation_sessions_channel_valid"),
        "conversation_sessions",
        type_="check",
    )
    op.drop_constraint(
        "uq_conversation_sessions_inbound_call",
        "conversation_sessions",
        type_="unique",
    )
    op.drop_constraint(
        "fk_conversation_sessions_inbound_call",
        "conversation_sessions",
        type_="foreignkey",
    )
    op.drop_column("conversation_sessions", "inbound_call_id")
    op.drop_column("conversation_sessions", "channel")
