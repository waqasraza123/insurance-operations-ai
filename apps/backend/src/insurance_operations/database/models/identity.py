from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
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


class AgencyEnvironment(StrEnum):
    DEVELOPMENT = "DEVELOPMENT"
    DEMO = "DEMO"
    PRODUCTION = "PRODUCTION"


class AppUserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class Agency(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    ArchivableMixin,
    Base,
):
    __tablename__ = "agencies"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 160",
            name="name_length_valid",
        ),
        CheckConstraint(
            "length(btrim(slug)) > 0 AND slug = lower(slug)",
            name="slug_lowercase",
        ),
        CheckConstraint(
            "environment_kind IN ('DEVELOPMENT', 'DEMO', 'PRODUCTION')",
            name="environment_kind_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint("slug", name="uq_agencies_slug"),
        Index("ix_agencies_environment_kind", "environment_kind"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    environment_kind: Mapped[str] = mapped_column(Text, nullable=False)


class AppUser(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "app_users"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(display_name)) BETWEEN 1 AND 160",
            name="display_name_length_valid",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="status_valid",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' AND disabled_at IS NULL) OR "
            "(status = 'DISABLED' AND disabled_at IS NOT NULL)",
            name="disabled_at_consistent",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint("auth_subject", name="uq_app_users_auth_subject"),
    )

    auth_subject: Mapped[UUID] = mapped_column(nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=AppUserStatus.ACTIVE.value,
        server_default=AppUserStatus.ACTIVE.value,
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


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
        Text,
        nullable=False,
        default=MembershipStatus.ACTIVE.value,
        server_default=MembershipStatus.ACTIVE.value,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
