from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from insurance_operations.database.models.base import (
    ArchivableMixin,
    Base,
    TimestampedMixin,
    UuidPrimaryKeyMixin,
    VersionedMixin,
)


class Customer(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    ArchivableMixin,
    Base,
):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("length(btrim(full_name)) > 0", name="full_name_not_blank"),
        CheckConstraint(
            "email IS NULL OR length(btrim(email)) > 0",
            name="email_not_blank",
        ),
        CheckConstraint(
            "phone IS NULL OR length(btrim(phone)) > 0",
            name="phone_not_blank",
        ),
        CheckConstraint(
            "address_state_code IS NULL OR address_state_code ~ '^[A-Z]{2}$'",
            name="state_code_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    search_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )


Index(
    "ix_customers_agency_archive_updated",
    Customer.agency_id,
    Customer.archived_at,
    Customer.updated_at.desc(),
    Customer.id,
)
Index(
    "ix_customers_search_text_trgm",
    Customer.search_text,
    postgresql_using="gin",
    postgresql_ops={"search_text": "gin_trgm_ops"},
)
