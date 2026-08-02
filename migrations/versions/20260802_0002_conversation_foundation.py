"""Create the generic conversation foundation.

Revision ID: 20260802_0002
Revises: 20260802_0001
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0002"
down_revision: str | None = "20260802_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
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
            "initiated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'REQUESTING'"),
        ),
        sa.Column(
            "provider_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "disclosure_accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "microphone_consent_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "synthetic_data_acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("maximum_duration_seconds", sa.SmallInteger(), nullable=False),
        sa.Column(
            "authorization_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "confirmation_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('REQUESTING', 'AUTHORIZED', 'REVIEW_PENDING', "
            "'CONFIRMED', 'FAILED', 'EXPIRED')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "maximum_duration_seconds BETWEEN 1 AND 180",
            name="duration_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(provider_metadata) = 'object'",
            name="provider_metadata_object",
        ),
        sa.CheckConstraint(
            "(status = 'CONFIRMED' AND confirmed_at IS NOT NULL) OR "
            "(status <> 'CONFIRMED' AND confirmed_at IS NULL)",
            name="confirmed_at_consistent",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
    )
    op.create_index(
        "ix_conversation_sessions_agency_created",
        "conversation_sessions",
        ["agency_id", "created_at"],
    )
    op.create_index(
        "ix_conversation_sessions_agency_status_expires",
        "conversation_sessions",
        ["agency_id", "status", "authorization_expires_at"],
    )
    op.create_index(
        "ix_conversation_sessions_agency_authorized",
        "conversation_sessions",
        ["agency_id", "authorized_at"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_conversation_sessions_mutable_metadata
        BEFORE UPDATE ON conversation_sessions
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )

    op.create_table(
        "conversation_intakes",
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
            "conversation_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "confirmation_source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'END_USER'"),
        ),
        sa.Column("intake_intent", sa.Text(), nullable=False),
        sa.Column(
            "confirmed_transcript",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "confirmation_source = 'END_USER'",
            name="confirmation_source_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(intake_intent)) BETWEEN 1 AND 2000",
            name="intake_intent_length_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(confirmed_transcript) = 'array' AND "
            "jsonb_array_length(confirmed_transcript) BETWEEN 2 AND 60",
            name="transcript_array_valid",
        ),
        sa.UniqueConstraint(
            "conversation_session_id",
            name="uq_conversation_intakes_session",
        ),
    )
    op.create_index(
        "ix_conversation_intakes_customer_confirmed",
        "conversation_intakes",
        ["customer_id", "confirmed_at"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_conversation_intake_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'conversation intakes are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_conversation_intakes_immutable
        BEFORE UPDATE OR DELETE ON conversation_intakes
        FOR EACH ROW EXECUTE FUNCTION reject_conversation_intake_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_conversation_intakes_immutable "
        "ON conversation_intakes"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_conversation_intake_mutation()")
    op.drop_index(
        "ix_conversation_intakes_customer_confirmed",
        table_name="conversation_intakes",
    )
    op.drop_table("conversation_intakes")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_conversation_sessions_mutable_metadata "
        "ON conversation_sessions"
    )
    op.drop_index(
        "ix_conversation_sessions_agency_authorized",
        table_name="conversation_sessions",
    )
    op.drop_index(
        "ix_conversation_sessions_agency_status_expires",
        table_name="conversation_sessions",
    )
    op.drop_index(
        "ix_conversation_sessions_agency_created",
        table_name="conversation_sessions",
    )
    op.drop_table("conversation_sessions")
