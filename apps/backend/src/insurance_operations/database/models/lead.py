from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from insurance_operations.database.models.base import (
    Base,
    TimestampedMixin,
    UuidPrimaryKeyMixin,
    VersionedMixin,
)


class LeadStatus(StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class LeadUrgency(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class HandoffRequestKind(StrEnum):
    CALLBACK = "CALLBACK"
    LIVE_TRANSFER = "LIVE_TRANSFER"


class HandoffContactMethod(StrEnum):
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    NO_PREFERENCE = "NO_PREFERENCE"


class HandoffStatus(StrEnum):
    REQUESTED = "REQUESTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AgencyLead(UuidPrimaryKeyMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "agency_leads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('NEW', 'CONTACTED', 'QUALIFIED', 'CLOSED', 'ARCHIVED')",
            name="status_valid",
        ),
        CheckConstraint(
            "urgency IN ('LOW', 'NORMAL', 'HIGH')",
            name="urgency_valid",
        ),
        CheckConstraint(
            "length(btrim(summary)) BETWEEN 1 AND 2000",
            name="summary_length_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "conversation_intake_id",
            name="uq_agency_leads_conversation_intake",
        ),
        Index(
            "ix_agency_leads_agency_status_created",
            "agency_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_agency_leads_customer_created",
            "customer_id",
            "created_at",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    conversation_intake_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation_intakes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=LeadStatus.NEW.value,
        server_default=LeadStatus.NEW.value,
    )
    urgency: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=LeadUrgency.NORMAL.value,
        server_default=LeadUrgency.NORMAL.value,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )


class LeadHandoffRequest(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "lead_handoff_requests"
    __table_args__ = (
        CheckConstraint(
            "request_kind IN ('CALLBACK', 'LIVE_TRANSFER')",
            name="request_kind_valid",
        ),
        CheckConstraint(
            "preferred_contact_method IN ('PHONE', 'EMAIL', 'NO_PREFERENCE')",
            name="contact_method_valid",
        ),
        CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 1000",
            name="reason_length_valid",
        ),
        CheckConstraint(
            "availability IS NULL OR length(btrim(availability)) BETWEEN 1 AND 500",
            name="availability_length_valid",
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'ACKNOWLEDGED', 'COMPLETED', 'CANCELLED')",
            name="status_valid",
        ),
        CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
            "(status <> 'COMPLETED' AND completed_at IS NULL)",
            name="completed_at_consistent",
        ),
        CheckConstraint(
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL) OR "
            "(status <> 'CANCELLED' AND cancelled_at IS NULL)",
            name="cancelled_at_consistent",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "inbound_call_id",
            name="uq_handoff_requests_inbound_call",
        ),
        Index(
            "ix_handoff_requests_lead_created",
            "lead_id",
            "created_at",
        ),
        Index(
            "ix_handoff_requests_agency_status",
            "agency_id",
            "status",
            "created_at",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("agency_leads.id", ondelete="RESTRICT"),
        nullable=False,
    )
    conversation_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation_sessions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    inbound_call_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "inbound_calls.id",
            name="fk_handoff_requests_inbound_call",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    request_kind: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_contact_method: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    availability: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfer_attempted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=HandoffStatus.REQUESTED.value,
        server_default=HandoffStatus.REQUESTED.value,
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
