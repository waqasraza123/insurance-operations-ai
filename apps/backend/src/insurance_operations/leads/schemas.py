from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from insurance_operations.conversations.schemas import ConversationTurn
from insurance_operations.customers import CustomerView
from insurance_operations.database.models.lead import (
    HandoffContactMethod,
    HandoffRequestKind,
    HandoffStatus,
    LeadStatus,
    LeadUrgency,
)


class LeadContactResponse(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None


class LeadSummaryResponse(BaseModel):
    id: UUID
    agency_id: UUID
    status: LeadStatus
    urgency: LeadUrgency
    summary: str
    intake_intent: str
    customer: LeadContactResponse
    open_handoff_count: int
    row_version: int
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadSummaryResponse]
    total: int
    limit: int
    offset: int


class LeadIntakeResponse(BaseModel):
    id: UUID
    conversation_session_id: UUID
    intake_intent: str
    transcript: list[ConversationTurn]
    confirmed_at: datetime


class LeadAuditEventResponse(BaseModel):
    id: UUID
    event_type: str
    summary: str
    details: dict[str, object]
    occurred_at: datetime
    correlation_id: UUID


class HandoffRequestResponse(BaseModel):
    id: UUID
    agency_id: UUID
    lead_id: UUID
    conversation_session_id: UUID | None
    inbound_call_id: UUID | None
    request_kind: HandoffRequestKind
    preferred_contact_method: HandoffContactMethod
    reason: str
    availability: str | None
    transfer_attempted: bool
    status: HandoffStatus
    completed_at: datetime | None
    cancelled_at: datetime | None
    row_version: int
    created_at: datetime
    updated_at: datetime


class LeadDetailResponse(BaseModel):
    id: UUID
    agency_id: UUID
    status: LeadStatus
    urgency: LeadUrgency
    summary: str
    customer: CustomerView
    intake: LeadIntakeResponse
    handoff_requests: list[HandoffRequestResponse]
    audit_history: list[LeadAuditEventResponse]
    row_version: int
    created_at: datetime
    updated_at: datetime


class LeadUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=2_000)
    urgency: LeadUrgency
    expected_row_version: int = Field(ge=1)


class LeadStatusInput(BaseModel):
    status: LeadStatus
    expected_row_version: int = Field(ge=1)


class HandoffRequestCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    request_kind: HandoffRequestKind
    preferred_contact_method: HandoffContactMethod
    reason: str = Field(min_length=1, max_length=1_000)
    availability: str | None = Field(default=None, min_length=1, max_length=500)


class HandoffStatusInput(BaseModel):
    status: HandoffStatus
    transfer_attempted: bool | None = None
    expected_row_version: int = Field(ge=1)
