"""Create agency-approved FAQs.

Revision ID: 20260808_0005
Revises: 20260808_0004
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0005"
down_revision: str | None = "20260808_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agency_approved_faqs",
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
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("approved_answer", sa.Text(), nullable=False),
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
            "length(btrim(question)) BETWEEN 1 AND 300",
            name="question_length_valid",
        ),
        sa.CheckConstraint(
            "length(normalized_question) BETWEEN 1 AND 300 "
            "AND normalized_question = lower(normalized_question)",
            name="normalized_question_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(approved_answer)) BETWEEN 1 AND 2000",
            name="answer_length_valid",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_valid",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.UniqueConstraint(
            "agency_id",
            "normalized_question",
            name="uq_agency_approved_faqs_agency_question",
        ),
    )
    op.create_index(
        "ix_agency_approved_faqs_agency_status",
        "agency_approved_faqs",
        ["agency_id", "status", "created_at"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_agency_approved_faqs_mutable_metadata
        BEFORE UPDATE ON agency_approved_faqs
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_agency_approved_faqs_mutable_metadata "
        "ON agency_approved_faqs"
    )
    op.drop_index(
        "ix_agency_approved_faqs_agency_status",
        table_name="agency_approved_faqs",
    )
    op.drop_table("agency_approved_faqs")
