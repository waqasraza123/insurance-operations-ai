import builtins
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.actors import ActorContext
from insurance_operations.conversations.schemas import ConversationTurn
from insurance_operations.customers import customer_view
from insurance_operations.database.models.conversation import ConversationIntake
from insurance_operations.database.models.customer import Customer
from insurance_operations.database.models.lead import (
    AgencyLead,
    HandoffContactMethod,
    HandoffRequestKind,
    HandoffStatus,
    LeadHandoffRequest,
    LeadStatus,
    LeadUrgency,
)
from insurance_operations.database.models.operations import (
    AuditActorType,
    AuditEvent,
    IdempotencyRecord,
    IdempotencyStatus,
)
from insurance_operations.errors import ApiError
from insurance_operations.leads.schemas import (
    HandoffRequestCreateInput,
    HandoffRequestResponse,
    HandoffStatusInput,
    LeadAuditEventResponse,
    LeadContactResponse,
    LeadDetailResponse,
    LeadIntakeResponse,
    LeadListResponse,
    LeadStatusInput,
    LeadSummaryResponse,
    LeadUpdateInput,
)

CREATE_HANDOFF_ROUTE_KEY = "POST /api/v1/development/leads/{lead_id}/handoff-requests"
OPEN_HANDOFF_STATUSES = {
    HandoffStatus.REQUESTED.value,
    HandoffStatus.ACKNOWLEDGED.value,
}
LEAD_TRANSITIONS = {
    LeadStatus.NEW.value: {
        LeadStatus.CONTACTED.value,
        LeadStatus.QUALIFIED.value,
        LeadStatus.CLOSED.value,
        LeadStatus.ARCHIVED.value,
    },
    LeadStatus.CONTACTED.value: {
        LeadStatus.QUALIFIED.value,
        LeadStatus.CLOSED.value,
        LeadStatus.ARCHIVED.value,
    },
    LeadStatus.QUALIFIED.value: {
        LeadStatus.CLOSED.value,
        LeadStatus.ARCHIVED.value,
    },
    LeadStatus.CLOSED.value: {LeadStatus.ARCHIVED.value},
    LeadStatus.ARCHIVED.value: set(),
}
HANDOFF_TRANSITIONS = {
    HandoffStatus.REQUESTED.value: {
        HandoffStatus.ACKNOWLEDGED.value,
        HandoffStatus.COMPLETED.value,
        HandoffStatus.CANCELLED.value,
    },
    HandoffStatus.ACKNOWLEDGED.value: {
        HandoffStatus.COMPLETED.value,
        HandoffStatus.CANCELLED.value,
    },
    HandoffStatus.COMPLETED.value: set(),
    HandoffStatus.CANCELLED.value: set(),
}


class LeadService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        idempotency_retention_hours: int,
    ) -> None:
        self._session_factory = session_factory
        self._idempotency_retention_hours = idempotency_retention_hours

    def list(
        self,
        *,
        actor: ActorContext,
        status: LeadStatus | None,
        limit: int,
        offset: int,
    ) -> LeadListResponse:
        filters = [AgencyLead.agency_id == actor.agency_id]
        if status is not None:
            filters.append(AgencyLead.status == status.value)
        open_handoff_count = (
            select(func.count())
            .select_from(LeadHandoffRequest)
            .where(
                LeadHandoffRequest.lead_id == AgencyLead.id,
                LeadHandoffRequest.status.in_(OPEN_HANDOFF_STATUSES),
            )
            .correlate(AgencyLead)
            .scalar_subquery()
        )
        statement = (
            select(AgencyLead, Customer, ConversationIntake, open_handoff_count)
            .join(Customer, Customer.id == AgencyLead.customer_id)
            .join(
                ConversationIntake,
                ConversationIntake.id == AgencyLead.conversation_intake_id,
            )
            .where(*filters)
            .order_by(AgencyLead.created_at.desc(), AgencyLead.id)
            .limit(limit)
            .offset(offset)
        )
        with self._session_factory() as session:
            rows = session.execute(statement).all()
            total = session.scalar(
                select(func.count()).select_from(AgencyLead).where(*filters)
            )
            return LeadListResponse(
                items=[
                    lead_summary_response(lead, customer, intake, handoff_count)
                    for lead, customer, intake, handoff_count in rows
                ],
                total=total or 0,
                limit=limit,
                offset=offset,
            )

    def get(self, *, actor: ActorContext, lead_id: UUID) -> LeadDetailResponse:
        with self._session_factory() as session:
            lead, customer, intake = self._get_detail_row(session, actor, lead_id)
            handoffs = session.scalars(
                select(LeadHandoffRequest)
                .where(
                    LeadHandoffRequest.agency_id == actor.agency_id,
                    LeadHandoffRequest.lead_id == lead.id,
                )
                .order_by(LeadHandoffRequest.created_at, LeadHandoffRequest.id)
            ).all()
            audits = session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.agency_id == actor.agency_id,
                    AuditEvent.customer_id == customer.id,
                )
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            ).all()
            return lead_detail_response(lead, customer, intake, handoffs, audits)

    def update(
        self,
        *,
        actor: ActorContext,
        lead_id: UUID,
        request: LeadUpdateInput,
        correlation_id: UUID,
    ) -> LeadDetailResponse:
        with self._session_factory() as session, session.begin():
            lead = self._get_owned_lead_for_update(session, actor, lead_id)
            require_version(
                actual=lead.row_version,
                expected=request.expected_row_version,
                resource="LEAD",
            )
            changed_fields = sorted(
                field
                for field, value in {
                    "summary": request.summary,
                    "urgency": request.urgency.value,
                }.items()
                if getattr(lead, field) != value
            )
            if changed_fields:
                lead.summary = request.summary
                lead.urgency = request.urgency.value
                lead.updated_by = actor.app_user_id
                session.flush()
                session.refresh(lead)
                session.add(
                    lead_audit_event(
                        actor=actor,
                        lead=lead,
                        event_type="LEAD_UPDATED",
                        summary="Lead details updated",
                        details={"changed_fields": changed_fields},
                        correlation_id=correlation_id,
                    )
                )
        return self.get(actor=actor, lead_id=lead_id)

    def set_status(
        self,
        *,
        actor: ActorContext,
        lead_id: UUID,
        request: LeadStatusInput,
        correlation_id: UUID,
    ) -> LeadDetailResponse:
        with self._session_factory() as session, session.begin():
            lead = self._get_owned_lead_for_update(session, actor, lead_id)
            require_version(
                actual=lead.row_version,
                expected=request.expected_row_version,
                resource="LEAD",
            )
            previous_status = lead.status
            if request.status.value not in LEAD_TRANSITIONS[previous_status]:
                raise invalid_transition(
                    resource="LEAD",
                    current=previous_status,
                    requested=request.status.value,
                )
            lead.status = request.status.value
            lead.updated_by = actor.app_user_id
            session.flush()
            session.refresh(lead)
            session.add(
                lead_audit_event(
                    actor=actor,
                    lead=lead,
                    event_type="LEAD_STATUS_CHANGED",
                    summary="Lead status changed",
                    details={
                        "previous_status": previous_status,
                        "status": lead.status,
                    },
                    correlation_id=correlation_id,
                )
            )
        return self.get(actor=actor, lead_id=lead_id)

    def list_handoffs(
        self,
        *,
        actor: ActorContext,
        lead_id: UUID,
    ) -> builtins.list[HandoffRequestResponse]:
        with self._session_factory() as session:
            self._get_owned_lead(session, actor, lead_id)
            handoffs = session.scalars(
                select(LeadHandoffRequest)
                .where(
                    LeadHandoffRequest.agency_id == actor.agency_id,
                    LeadHandoffRequest.lead_id == lead_id,
                )
                .order_by(LeadHandoffRequest.created_at, LeadHandoffRequest.id)
            ).all()
            return [handoff_response(handoff) for handoff in handoffs]

    def create_handoff(
        self,
        *,
        actor: ActorContext,
        lead_id: UUID,
        request: HandoffRequestCreateInput,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[HandoffRequestResponse, bool]:
        now = datetime.now(UTC)
        fingerprint = handoff_fingerprint(lead_id, request)
        idempotency_insert = (
            insert(IdempotencyRecord)
            .values(
                agency_id=actor.agency_id,
                actor_scope_type="APP_USER",
                actor_scope_id=actor.app_user_id,
                route_key=CREATE_HANDOFF_ROUTE_KEY,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                status=IdempotencyStatus.IN_PROGRESS.value,
                expires_at=now + timedelta(hours=self._idempotency_retention_hours),
            )
            .on_conflict_do_nothing(constraint="uq_idempotency_records_scope")
            .returning(IdempotencyRecord.id)
        )
        with self._session_factory() as session, session.begin():
            record_id = session.scalar(idempotency_insert)
            if record_id is None:
                existing = session.scalar(
                    select(IdempotencyRecord)
                    .where(
                        IdempotencyRecord.actor_scope_type == "APP_USER",
                        IdempotencyRecord.actor_scope_id == actor.app_user_id,
                        IdempotencyRecord.route_key == CREATE_HANDOFF_ROUTE_KEY,
                        IdempotencyRecord.idempotency_key == idempotency_key,
                    )
                    .with_for_update()
                )
                return replay_handoff(existing, fingerprint), True

            lead, customer, intake = self._get_detail_row(
                session,
                actor,
                lead_id,
                for_update=True,
            )
            validate_contact_method(customer, request)
            handoff = LeadHandoffRequest(
                agency_id=actor.agency_id,
                lead_id=lead.id,
                conversation_session_id=intake.conversation_session_id,
                request_kind=request.request_kind.value,
                preferred_contact_method=request.preferred_contact_method.value,
                reason=request.reason,
                availability=request.availability,
                transfer_attempted=False,
                status=HandoffStatus.REQUESTED.value,
                created_by=actor.app_user_id,
                updated_by=actor.app_user_id,
            )
            session.add(handoff)
            session.flush()
            response = handoff_response(handoff)
            session.add(
                lead_audit_event(
                    actor=actor,
                    lead=lead,
                    event_type="LEAD_HANDOFF_REQUESTED",
                    summary="Human handoff requested",
                    details={
                        "handoff_request_id": str(handoff.id),
                        "request_kind": handoff.request_kind,
                        "preferred_contact_method": handoff.preferred_contact_method,
                    },
                    correlation_id=correlation_id,
                )
            )
            idempotency_record = session.get(IdempotencyRecord, record_id)
            if idempotency_record is None:
                raise RuntimeError("idempotency record was not persisted")
            idempotency_record.status = IdempotencyStatus.COMPLETED.value
            idempotency_record.response_status = 201
            idempotency_record.response_body = response.model_dump(mode="json")
            idempotency_record.resource_type = "LEAD_HANDOFF_REQUEST"
            idempotency_record.resource_id = handoff.id
            idempotency_record.completed_at = now
            return response, False

    def set_handoff_status(
        self,
        *,
        actor: ActorContext,
        handoff_id: UUID,
        request: HandoffStatusInput,
        correlation_id: UUID,
    ) -> HandoffRequestResponse:
        now = datetime.now(UTC)
        with self._session_factory() as session, session.begin():
            handoff = session.scalar(
                select(LeadHandoffRequest)
                .where(
                    LeadHandoffRequest.id == handoff_id,
                    LeadHandoffRequest.agency_id == actor.agency_id,
                )
                .with_for_update()
            )
            if handoff is None:
                raise ApiError(
                    status_code=404,
                    code="HANDOFF_REQUEST_NOT_FOUND",
                    message="The handoff request was not found",
                )
            require_version(
                actual=handoff.row_version,
                expected=request.expected_row_version,
                resource="HANDOFF_REQUEST",
            )
            previous_status = handoff.status
            if request.status.value not in HANDOFF_TRANSITIONS[previous_status]:
                raise invalid_transition(
                    resource="HANDOFF_REQUEST",
                    current=previous_status,
                    requested=request.status.value,
                )
            if request.transfer_attempted is not None:
                if handoff.request_kind != HandoffRequestKind.LIVE_TRANSFER.value:
                    raise ApiError(
                        status_code=422,
                        code="TRANSFER_NOT_APPLICABLE",
                        message=(
                            "Transfer attempts apply only to live-transfer requests"
                        ),
                    )
                handoff.transfer_attempted = request.transfer_attempted
            handoff.status = request.status.value
            handoff.completed_at = (
                now if request.status is HandoffStatus.COMPLETED else None
            )
            handoff.cancelled_at = (
                now if request.status is HandoffStatus.CANCELLED else None
            )
            handoff.updated_by = actor.app_user_id
            session.flush()
            session.refresh(handoff)
            lead = self._get_owned_lead(session, actor, handoff.lead_id)
            session.add(
                lead_audit_event(
                    actor=actor,
                    lead=lead,
                    event_type="LEAD_HANDOFF_STATUS_CHANGED",
                    summary="Human handoff status changed",
                    details={
                        "handoff_request_id": str(handoff.id),
                        "previous_status": previous_status,
                        "status": handoff.status,
                        "transfer_attempted": handoff.transfer_attempted,
                    },
                    correlation_id=correlation_id,
                )
            )
            return handoff_response(handoff)

    @staticmethod
    def _get_owned_lead(
        session: Session,
        actor: ActorContext,
        lead_id: UUID,
    ) -> AgencyLead:
        lead = session.scalar(
            select(AgencyLead).where(
                AgencyLead.id == lead_id,
                AgencyLead.agency_id == actor.agency_id,
            )
        )
        if lead is None:
            raise lead_not_found()
        return lead

    @staticmethod
    def _get_owned_lead_for_update(
        session: Session,
        actor: ActorContext,
        lead_id: UUID,
    ) -> AgencyLead:
        lead = session.scalar(
            select(AgencyLead)
            .where(
                AgencyLead.id == lead_id,
                AgencyLead.agency_id == actor.agency_id,
            )
            .with_for_update()
        )
        if lead is None:
            raise lead_not_found()
        return lead

    @staticmethod
    def _get_detail_row(
        session: Session,
        actor: ActorContext,
        lead_id: UUID,
        *,
        for_update: bool = False,
    ) -> tuple[AgencyLead, Customer, ConversationIntake]:
        statement = (
            select(AgencyLead, Customer, ConversationIntake)
            .join(Customer, Customer.id == AgencyLead.customer_id)
            .join(
                ConversationIntake,
                ConversationIntake.id == AgencyLead.conversation_intake_id,
            )
            .where(
                AgencyLead.id == lead_id,
                AgencyLead.agency_id == actor.agency_id,
                Customer.agency_id == actor.agency_id,
                ConversationIntake.agency_id == actor.agency_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=AgencyLead)
        row = session.execute(statement).one_or_none()
        if row is None:
            raise lead_not_found()
        lead, customer, intake = row
        return lead, customer, intake


def lead_summary_response(
    lead: AgencyLead,
    customer: Customer,
    intake: ConversationIntake,
    open_handoff_count: int,
) -> LeadSummaryResponse:
    return LeadSummaryResponse(
        id=lead.id,
        agency_id=lead.agency_id,
        status=LeadStatus(lead.status),
        urgency=LeadUrgency(lead.urgency),
        summary=lead.summary,
        intake_intent=intake.intake_intent,
        customer=LeadContactResponse(
            id=customer.id,
            full_name=customer.full_name,
            email=customer.email,
            phone=customer.phone,
        ),
        open_handoff_count=open_handoff_count,
        row_version=lead.row_version,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def lead_detail_response(
    lead: AgencyLead,
    customer: Customer,
    intake: ConversationIntake,
    handoffs: Sequence[LeadHandoffRequest],
    audits: Sequence[AuditEvent],
) -> LeadDetailResponse:
    return LeadDetailResponse(
        id=lead.id,
        agency_id=lead.agency_id,
        status=LeadStatus(lead.status),
        urgency=LeadUrgency(lead.urgency),
        summary=lead.summary,
        customer=customer_view(customer),
        intake=LeadIntakeResponse(
            id=intake.id,
            conversation_session_id=intake.conversation_session_id,
            intake_intent=intake.intake_intent,
            transcript=[
                ConversationTurn.model_validate(turn)
                for turn in intake.confirmed_transcript
            ],
            confirmed_at=intake.confirmed_at,
        ),
        handoff_requests=[handoff_response(handoff) for handoff in handoffs],
        audit_history=[
            LeadAuditEventResponse(
                id=audit.id,
                event_type=audit.event_type,
                summary=audit.summary,
                details=audit.details,
                occurred_at=audit.occurred_at,
                correlation_id=audit.correlation_id,
            )
            for audit in audits
        ],
        row_version=lead.row_version,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def handoff_response(handoff: LeadHandoffRequest) -> HandoffRequestResponse:
    return HandoffRequestResponse(
        id=handoff.id,
        agency_id=handoff.agency_id,
        lead_id=handoff.lead_id,
        conversation_session_id=handoff.conversation_session_id,
        inbound_call_id=handoff.inbound_call_id,
        request_kind=HandoffRequestKind(handoff.request_kind),
        preferred_contact_method=HandoffContactMethod(handoff.preferred_contact_method),
        reason=handoff.reason,
        availability=handoff.availability,
        transfer_attempted=handoff.transfer_attempted,
        status=HandoffStatus(handoff.status),
        completed_at=handoff.completed_at,
        cancelled_at=handoff.cancelled_at,
        row_version=handoff.row_version,
        created_at=handoff.created_at,
        updated_at=handoff.updated_at,
    )


def validate_contact_method(
    customer: Customer,
    request: HandoffRequestCreateInput,
) -> None:
    if request.request_kind is HandoffRequestKind.LIVE_TRANSFER:
        return
    if (
        request.preferred_contact_method is HandoffContactMethod.PHONE
        and customer.phone is None
    ):
        raise ApiError(
            status_code=422,
            code="HANDOFF_PHONE_REQUIRED",
            message="A phone number is required for a phone callback",
        )
    if (
        request.preferred_contact_method is HandoffContactMethod.EMAIL
        and customer.email is None
    ):
        raise ApiError(
            status_code=422,
            code="HANDOFF_EMAIL_REQUIRED",
            message="An email address is required for an email callback",
        )


def require_version(*, actual: int, expected: int, resource: str) -> None:
    if actual != expected:
        raise ApiError(
            status_code=409,
            code=f"{resource}_VERSION_CONFLICT",
            message="The resource was changed by another request",
            details={"current_row_version": actual},
        )


def invalid_transition(*, resource: str, current: str, requested: str) -> ApiError:
    return ApiError(
        status_code=409,
        code=f"{resource}_STATUS_TRANSITION_INVALID",
        message="The requested status transition is not allowed",
        details={"current_status": current, "requested_status": requested},
    )


def lead_not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="LEAD_NOT_FOUND",
        message="The lead was not found",
    )


def lead_audit_event(
    *,
    actor: ActorContext,
    lead: AgencyLead,
    event_type: str,
    summary: str,
    details: dict[str, object],
    correlation_id: UUID,
) -> AuditEvent:
    return AuditEvent(
        agency_id=actor.agency_id,
        actor_type=AuditActorType.STAFF.value,
        actor_user_id=actor.app_user_id,
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        customer_id=lead.customer_id,
        summary=summary,
        details={"lead_id": str(lead.id), **details},
        correlation_id=correlation_id,
        event_version=1,
    )


def handoff_fingerprint(lead_id: UUID, request: HandoffRequestCreateInput) -> str:
    canonical_request = json.dumps(
        {
            "lead_id": str(lead_id),
            "request": request.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_request.encode()).hexdigest()


def replay_handoff(
    record: IdempotencyRecord | None,
    fingerprint: str,
) -> HandoffRequestResponse:
    if record is None:
        raise ApiError(
            status_code=409,
            code="IDEMPOTENCY_CONFLICT",
            message="The idempotent request could not be resolved",
        )
    if record.request_fingerprint != fingerprint:
        raise ApiError(
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            message="The idempotency key was used for another request",
        )
    if (
        record.status != IdempotencyStatus.COMPLETED.value
        or record.response_body is None
    ):
        raise ApiError(
            status_code=409,
            code="OPERATION_IN_PROGRESS",
            message="The original handoff request is still in progress",
        )
    return HandoffRequestResponse.model_validate(record.response_body)
