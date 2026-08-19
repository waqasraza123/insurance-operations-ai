from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.database.models.conversation import ConversationSession
from insurance_operations.database.models.lead import (
    AgencyLead,
    HandoffRequestKind,
    HandoffStatus,
    LeadHandoffRequest,
    LeadUrgency,
)
from insurance_operations.database.models.telephony import (
    InboundCall,
    InboundCallStatus,
)


class PhoneDemoState(StrEnum):
    READY = "READY"
    RINGING = "RINGING"
    IN_PROGRESS = "IN_PROGRESS"
    LEAD_CREATED = "LEAD_CREATED"
    TRANSFERRED = "TRANSFERRED"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"
    FAILED = "FAILED"


class PhoneDemoStatusResponse(BaseModel):
    state: PhoneDemoState
    received_at: datetime | None = None
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    consent_completed: bool = False
    lead_created: bool = False
    urgency: LeadUrgency | None = None
    handoff_kind: HandoffRequestKind | None = None
    handoff_status: HandoffStatus | None = None


class PhoneDemoService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        result_ttl_minutes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._result_ttl = timedelta(minutes=result_ttl_minutes)
        self._clock = clock or (lambda: datetime.now(UTC))

    def latest_status(self, *, agency_id: UUID) -> PhoneDemoStatusResponse:
        cutoff = self._clock() - self._result_ttl
        with self._session_factory() as session:
            inbound_call = session.scalar(
                select(InboundCall)
                .where(
                    InboundCall.agency_id == agency_id,
                    InboundCall.received_at >= cutoff,
                )
                .order_by(InboundCall.received_at.desc(), InboundCall.id.desc())
                .limit(1)
            )
            if inbound_call is None:
                return PhoneDemoStatusResponse(state=PhoneDemoState.READY)

            conversation_session = session.scalar(
                select(ConversationSession).where(
                    ConversationSession.inbound_call_id == inbound_call.id
                )
            )
            lead = (
                session.get(AgencyLead, inbound_call.lead_id)
                if inbound_call.lead_id is not None
                else None
            )
            handoff = session.scalar(
                select(LeadHandoffRequest).where(
                    LeadHandoffRequest.inbound_call_id == inbound_call.id
                )
            )
            return PhoneDemoStatusResponse(
                state=demo_state(inbound_call, lead),
                received_at=inbound_call.received_at,
                answered_at=inbound_call.answered_at,
                ended_at=inbound_call.ended_at,
                consent_completed=(
                    conversation_session is not None
                    and conversation_session.authorized_at is not None
                ),
                lead_created=lead is not None,
                urgency=LeadUrgency(lead.urgency) if lead is not None else None,
                handoff_kind=(
                    HandoffRequestKind(handoff.request_kind)
                    if handoff is not None
                    else None
                ),
                handoff_status=(
                    HandoffStatus(handoff.status) if handoff is not None else None
                ),
            )


def demo_state(
    inbound_call: InboundCall,
    lead: AgencyLead | None,
) -> PhoneDemoState:
    status = InboundCallStatus(inbound_call.status)
    if status is InboundCallStatus.RECEIVED:
        return PhoneDemoState.RINGING
    if status in {
        InboundCallStatus.CONNECTED,
        InboundCallStatus.TRANSFER_PENDING,
        InboundCallStatus.CALLBACK_PENDING,
    }:
        return PhoneDemoState.IN_PROGRESS
    if status is InboundCallStatus.TRANSFERRED:
        return PhoneDemoState.TRANSFERRED
    if status is InboundCallStatus.CALLBACK_REQUESTED:
        return PhoneDemoState.CALLBACK_REQUESTED
    if status is InboundCallStatus.FAILED:
        return PhoneDemoState.FAILED
    if lead is not None:
        return PhoneDemoState.LEAD_CREATED
    return PhoneDemoState.FAILED
