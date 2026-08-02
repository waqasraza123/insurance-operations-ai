from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
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


class IdempotencyStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("length(btrim(actor_type)) > 0", name="actor_type_not_blank"),
        CheckConstraint("length(btrim(event_type)) > 0", name="event_type_not_blank"),
        CheckConstraint("length(btrim(target_type)) > 0", name="target_type_not_blank"),
        CheckConstraint("length(btrim(summary)) > 0", name="summary_not_blank"),
        CheckConstraint("event_version > 0", name="event_version_positive"),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    event_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    correlation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


Index(
    "ix_audit_events_agency_created",
    AuditEvent.agency_id,
    AuditEvent.created_at.desc(),
    AuditEvent.id,
)
Index(
    "ix_audit_events_target_created",
    AuditEvent.target_type,
    AuditEvent.target_id,
    AuditEvent.created_at.desc(),
)
Index("ix_audit_events_correlation", AuditEvent.correlation_id)


class IdempotencyRecord(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(environment_kind)) > 0",
            name="environment_not_blank",
        ),
        CheckConstraint(
            "length(btrim(actor_identifier)) > 0",
            name="actor_identifier_not_blank",
        ),
        CheckConstraint("length(btrim(route_key)) > 0", name="route_key_not_blank"),
        CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 128",
            name="key_length_valid",
        ),
        CheckConstraint("length(request_hash) = 64", name="request_hash_valid"),
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="status_valid",
        ),
        CheckConstraint(
            "response_status_code IS NULL OR response_status_code BETWEEN 100 AND 599",
            name="response_status_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "agency_id",
            "environment_kind",
            "actor_identifier",
            "route_key",
            "idempotency_key",
            name="uq_idempotency_records_scope",
        ),
        Index("ix_idempotency_records_expiry", "expires_at", "status"),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    environment_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    route_key: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IdempotencyStatus.IN_PROGRESS.value,
        server_default=IdempotencyStatus.IN_PROGRESS.value,
    )
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
