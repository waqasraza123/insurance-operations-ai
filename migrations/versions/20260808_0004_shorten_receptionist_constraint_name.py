"""Shorten the receptionist categories constraint name.

Revision ID: 20260808_0004
Revises: 20260807_0003
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260808_0004"
down_revision: str | None = "20260807_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRUNCATED_CONSTRAINT_NAME = (
    "ck_agency_receptionist_settings_supported_categories_ar_dbae"
)
CURRENT_CONSTRAINT_NAME = "ck_agency_receptionist_settings_supported_categories_valid"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agency_receptionist_settings "
        f"RENAME CONSTRAINT {TRUNCATED_CONSTRAINT_NAME} "
        f"TO {CURRENT_CONSTRAINT_NAME}"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agency_receptionist_settings "
        f"RENAME CONSTRAINT {CURRENT_CONSTRAINT_NAME} "
        f"TO {TRUNCATED_CONSTRAINT_NAME}"
    )
