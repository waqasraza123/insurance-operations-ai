from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from insurance_operations.database.models.base import (
    Base,
    TimestampedMixin,
    UuidPrimaryKeyMixin,
    VersionedMixin,
)


class AgencyReceptionistSettings(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "agency_receptionist_settings"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(public_name)) BETWEEN 1 AND 160",
            name="public_name_length_valid",
        ),
        CheckConstraint(
            "length(btrim(greeting)) BETWEEN 1 AND 600",
            name="greeting_length_valid",
        ),
        CheckConstraint(
            "length(btrim(office_hours)) BETWEEN 1 AND 1000",
            name="office_hours_length_valid",
        ),
        CheckConstraint(
            "contact_email IS NULL OR length(btrim(contact_email)) BETWEEN 3 AND 320",
            name="contact_email_length_valid",
        ),
        CheckConstraint(
            "contact_phone IS NULL OR length(btrim(contact_phone)) BETWEEN 7 AND 32",
            name="contact_phone_length_valid",
        ),
        CheckConstraint(
            "contact_email IS NOT NULL OR contact_phone IS NOT NULL",
            name="contact_method_required",
        ),
        CheckConstraint(
            "jsonb_typeof(supported_insurance_categories) = 'array' AND "
            "jsonb_array_length(supported_insurance_categories) BETWEEN 1 AND 20",
            name="supported_categories_valid",
        ),
        CheckConstraint(
            "length(btrim(escalation_message)) BETWEEN 1 AND 600",
            name="escalation_message_length_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "agency_id",
            name="uq_agency_receptionist_settings_agency",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    public_name: Mapped[str] = mapped_column(Text, nullable=False)
    greeting: Mapped[str] = mapped_column(Text, nullable=False)
    office_hours: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    supported_insurance_categories: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
    )
    escalation_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
