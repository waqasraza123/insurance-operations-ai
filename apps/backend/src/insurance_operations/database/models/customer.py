from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, Uuid
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
        CheckConstraint(
            "length(btrim(full_name)) BETWEEN 1 AND 200",
            name="full_name_length_valid",
        ),
        CheckConstraint(
            "state_code IS NULL OR length(state_code) = 2",
            name="state_code_length_valid",
        ),
        CheckConstraint(
            "length(country_code) = 2",
            name="country_code_length_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    demo_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_line1: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_line2: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="US",
        server_default="US",
    )
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
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
