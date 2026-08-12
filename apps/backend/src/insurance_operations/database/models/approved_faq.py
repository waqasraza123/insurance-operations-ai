from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from insurance_operations.database.models.base import (
    Base,
    TimestampedMixin,
    UuidPrimaryKeyMixin,
    VersionedMixin,
)


class ApprovedFaqStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AgencyApprovedFaq(
    UuidPrimaryKeyMixin,
    TimestampedMixin,
    VersionedMixin,
    Base,
):
    __tablename__ = "agency_approved_faqs"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(question)) BETWEEN 1 AND 300",
            name="question_length_valid",
        ),
        CheckConstraint(
            "length(normalized_question) BETWEEN 1 AND 300 "
            "AND normalized_question = lower(normalized_question)",
            name="normalized_question_valid",
        ),
        CheckConstraint(
            "length(btrim(approved_answer)) BETWEEN 1 AND 2000",
            name="answer_length_valid",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="status_valid",
        ),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        UniqueConstraint(
            "agency_id",
            "normalized_question",
            name="uq_agency_approved_faqs_agency_question",
        ),
        Index(
            "ix_agency_approved_faqs_agency_status",
            "agency_id",
            "status",
            "created_at",
        ),
    )

    agency_id: Mapped[UUID] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    approved_answer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ApprovedFaqStatus.INACTIVE.value,
        server_default=ApprovedFaqStatus.INACTIVE.value,
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
