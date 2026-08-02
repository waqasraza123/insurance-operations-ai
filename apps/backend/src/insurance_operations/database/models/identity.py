from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from insurance_operations.database.models.base import (
    ArchivableMixin,
    Base,
    TimestampedMixin,
    UuidPrimaryKeyMixin,
    VersionedMixin,
)


class MembershipStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Agency(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    ArchivableMixin,
    Base,
):
    __tablename__ = "agencies"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)


class AppUser(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    ArchivableMixin,
    Base,
):
    __tablename__ = "app_users"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(auth_subject)) > 0",
            name="auth_subject_not_blank",
        ),
        CheckConstraint(
            "email IS NULL OR length(btrim(email)) > 0",
            name="email_not_blank",
        ),
        CheckConstraint(
            "display_name IS NULL OR length(btrim(display_name)) > 0",
            name="display_name_not_blank",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint("auth_subject", name="uq_app_users_auth_subject"),
    )

    auth_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)


class AgencyMembership(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "agency_memberships"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "agency_id",
            "app_user_id",
            name="uq_agency_memberships_agency_user",
        ),
        Index("ix_agency_memberships_user_status", "app_user_id", "status"),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    app_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MembershipStatus.ACTIVE.value,
        server_default=MembershipStatus.ACTIVE.value,
    )
