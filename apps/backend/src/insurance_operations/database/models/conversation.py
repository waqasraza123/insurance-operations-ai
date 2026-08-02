from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from insurance_operations.database.models.base import (
    Base,
    TimestampedMixin,
    UuidPrimaryKeyMixin,
    VersionedMixin,
)


class ConversationSessionStatus(StrEnum):
    REQUESTING = "REQUESTING"
    AUTHORIZED = "AUTHORIZED"
    REVIEW_PENDING = "REVIEW_PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ConversationSession(UuidPrimaryKeyMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('REQUESTING', 'AUTHORIZED', 'REVIEW_PENDING', "
            "'CONFIRMED', 'FAILED', 'EXPIRED')",
            name="status_valid",
        ),
        CheckConstraint(
            "maximum_duration_seconds BETWEEN 1 AND 180",
            name="duration_valid",
        ),
        CheckConstraint(
            "jsonb_typeof(provider_metadata) = 'object'",
            name="provider_metadata_object",
        ),
        CheckConstraint(
            "(status = 'CONFIRMED' AND confirmed_at IS NOT NULL) OR "
            "(status <> 'CONFIRMED' AND confirmed_at IS NULL)",
            name="confirmed_at_consistent",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        Index(
            "ix_conversation_sessions_agency_created",
            "agency_id",
            "created_at",
        ),
        Index(
            "ix_conversation_sessions_agency_status_expires",
            "agency_id",
            "status",
            "authorization_expires_at",
        ),
        Index(
            "ix_conversation_sessions_agency_authorized",
            "agency_id",
            "authorized_at",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    initiated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ConversationSessionStatus.REQUESTING.value,
        server_default=ConversationSessionStatus.REQUESTING.value,
    )
    provider_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    disclosure_accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    microphone_consent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    synthetic_data_acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    maximum_duration_seconds: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    authorization_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    confirmation_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    authorized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConversationIntake(UuidPrimaryKeyMixin, Base):
    __tablename__ = "conversation_intakes"
    __table_args__ = (
        CheckConstraint(
            "confirmation_source = 'END_USER'",
            name="confirmation_source_valid",
        ),
        CheckConstraint(
            "length(btrim(intake_intent)) BETWEEN 1 AND 2000",
            name="intake_intent_length_valid",
        ),
        CheckConstraint(
            "jsonb_typeof(confirmed_transcript) = 'array' AND "
            "jsonb_array_length(confirmed_transcript) BETWEEN 2 AND 60",
            name="transcript_array_valid",
        ),
        UniqueConstraint(
            "conversation_session_id",
            name="uq_conversation_intakes_session",
        ),
        Index(
            "ix_conversation_intakes_customer_confirmed",
            "customer_id",
            "confirmed_at",
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
    conversation_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    confirmation_source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="END_USER",
        server_default="END_USER",
    )
    intake_intent: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_transcript: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
