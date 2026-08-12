"""Create agency receptionist settings.

Revision ID: 20260807_0003
Revises: 20260802_0002
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0003"
down_revision: str | None = "20260802_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agency_receptionist_settings",
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
        sa.Column("public_name", sa.Text(), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=False),
        sa.Column("office_hours", sa.Text(), nullable=False),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column(
            "supported_insurance_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("escalation_message", sa.Text(), nullable=False),
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
            "length(btrim(public_name)) BETWEEN 1 AND 160",
            name="public_name_length_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(greeting)) BETWEEN 1 AND 600",
            name="greeting_length_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(office_hours)) BETWEEN 1 AND 1000",
            name="office_hours_length_valid",
        ),
        sa.CheckConstraint(
            "contact_email IS NULL OR length(btrim(contact_email)) BETWEEN 3 AND 320",
            name="contact_email_length_valid",
        ),
        sa.CheckConstraint(
            "contact_phone IS NULL OR length(btrim(contact_phone)) BETWEEN 7 AND 32",
            name="contact_phone_length_valid",
        ),
        sa.CheckConstraint(
            "contact_email IS NOT NULL OR contact_phone IS NOT NULL",
            name="contact_method_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(supported_insurance_categories) = 'array' AND "
            "jsonb_array_length(supported_insurance_categories) BETWEEN 1 AND 20",
            name="supported_categories_array_valid",
        ),
        sa.CheckConstraint(
            "length(btrim(escalation_message)) BETWEEN 1 AND 600",
            name="escalation_message_length_valid",
        ),
        sa.CheckConstraint("row_version > 0", name="row_version_positive"),
        sa.UniqueConstraint(
            "agency_id",
            name="uq_agency_receptionist_settings_agency",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER trg_agency_receptionist_settings_mutable_metadata
        BEFORE UPDATE ON agency_receptionist_settings
        FOR EACH ROW EXECUTE FUNCTION set_mutable_record_metadata()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_agency_receptionist_settings_mutable_metadata "
        "ON agency_receptionist_settings"
    )
    op.drop_table("agency_receptionist_settings")
