from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from insurance_operations.database.models.base import (
    Base,
    TimestampedMixin,
    UuidPrimaryKeyMixin,
    VersionedMixin,
)


class InboundNumberStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class InboundCallStatus(StrEnum):
    RECEIVED = "RECEIVED"
    CONNECTED = "CONNECTED"
    TRANSFER_PENDING = "TRANSFER_PENDING"
    TRANSFERRED = "TRANSFERRED"
    CALLBACK_PENDING = "CALLBACK_PENDING"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgencyCallPolicy(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "agency_call_policies"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(timezone)) BETWEEN 1 AND 100",
            name="timezone_length_valid",
        ),
        CheckConstraint(
            "transfer_destination_e164 IS NULL OR "
            "length(transfer_destination_e164) BETWEEN 8 AND 16",
            name="transfer_number_length_valid",
        ),
        CheckConstraint(
            "transfer_enabled = false OR transfer_destination_e164 IS NOT NULL",
            name="transfer_destination_required",
        ),
        CheckConstraint(
            "transfer_ring_timeout_seconds BETWEEN 10 AND 60",
            name="ring_timeout_valid",
        ),
        CheckConstraint(
            "max_concurrent_calls BETWEEN 1 AND 20",
            name="concurrent_limit_valid",
        ),
        CheckConstraint(
            "daily_call_limit BETWEEN 1 AND 1000",
            name="daily_limit_valid",
        ),
        CheckConstraint(
            "jsonb_typeof(availability_windows) = 'array'",
            name="availability_windows_array",
        ),
        CheckConstraint(
            "length(btrim(after_hours_message)) BETWEEN 1 AND 600",
            name="after_hours_message_valid",
        ),
        CheckConstraint(
            "length(btrim(unavailable_message)) BETWEEN 1 AND 600",
            name="unavailable_message_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint("agency_id", name="uq_agency_call_policies_agency"),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inbound_enabled: Mapped[bool]
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    availability_windows: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    transfer_enabled: Mapped[bool]
    transfer_destination_e164: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    transfer_ring_timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_call_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    callback_fallback_enabled: Mapped[bool]
    after_hours_message: Mapped[str] = mapped_column(Text, nullable=False)
    unavailable_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )


class AgencyInboundNumber(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "agency_inbound_numbers"
    __table_args__ = (
        CheckConstraint(
            "length(phone_number_e164) BETWEEN 8 AND 16",
            name="phone_number_length_valid",
        ),
        CheckConstraint(
            "length(btrim(label)) BETWEEN 1 AND 120",
            name="label_length_valid",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "phone_number_e164",
            name="uq_agency_inbound_numbers_phone",
        ),
        Index(
            "ix_inbound_numbers_agency_status",
            "agency_id",
            "status",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    phone_number_e164: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=InboundNumberStatus.INACTIVE.value,
        server_default=InboundNumberStatus.INACTIVE.value,
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )


class InboundCall(UuidPrimaryKeyMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "inbound_calls"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RECEIVED', 'CONNECTED', 'TRANSFER_PENDING', "
            "'TRANSFERRED', 'CALLBACK_PENDING', 'CALLBACK_REQUESTED', "
            "'COMPLETED', 'FAILED')",
            name="status_valid",
        ),
        CheckConstraint(
            "caller_number_e164 IS NULL OR length(caller_number_e164) BETWEEN 8 AND 16",
            name="caller_number_length_valid",
        ),
        CheckConstraint(
            "length(btrim(adapter_name)) BETWEEN 1 AND 80",
            name="adapter_name_length_valid",
        ),
        CheckConstraint(
            "length(btrim(source_call_reference)) BETWEEN 1 AND 200",
            name="source_reference_length_valid",
        ),
        CheckConstraint(
            "failure_code IS NULL OR length(failure_code) BETWEEN 1 AND 80",
            name="failure_code_length_valid",
        ),
        CheckConstraint(
            "answered_at IS NULL OR answered_at >= received_at",
            name="answered_time_valid",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= received_at",
            name="ended_time_valid",
        ),
        CheckConstraint(
            "(status = 'FAILED' AND failure_code IS NOT NULL) OR "
            "(status <> 'FAILED' AND failure_code IS NULL)",
            name="failure_code_consistent",
        ),
        CheckConstraint(
            "jsonb_typeof(adapter_metadata) = 'object'",
            name="adapter_metadata_object",
        ),
        CheckConstraint(
            "jsonb_typeof(policy_snapshot) = 'object'",
            name="policy_snapshot_object",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "adapter_name",
            "source_call_reference",
            name="uq_inbound_calls_adapter_reference",
        ),
        Index(
            "ix_inbound_calls_agency_status_created",
            "agency_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_inbound_calls_number_created",
            "inbound_number_id",
            "created_at",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inbound_number_id: Mapped[UUID] = mapped_column(
        ForeignKey("agency_inbound_numbers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agency_leads.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=InboundCallStatus.RECEIVED.value,
        server_default=InboundCallStatus.RECEIVED.value,
    )
    caller_number_e164: Mapped[str | None] = mapped_column(Text, nullable=True)
    adapter_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_call_reference: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)


class InboundCallEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "inbound_call_events"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(event_type)) BETWEEN 1 AND 80",
            name="event_type_length_valid",
        ),
        CheckConstraint(
            "length(btrim(event_key)) BETWEEN 1 AND 200",
            name="event_key_length_valid",
        ),
        CheckConstraint(
            "jsonb_typeof(details) = 'object'",
            name="details_object",
        ),
        UniqueConstraint(
            "inbound_call_id",
            "event_key",
            name="uq_inbound_call_events_call_key",
        ),
        Index(
            "ix_inbound_call_events_call_occurred",
            "inbound_call_id",
            "occurred_at",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inbound_call_id: Mapped[UUID] = mapped_column(
        ForeignKey("inbound_calls.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
