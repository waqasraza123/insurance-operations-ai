from datetime import UTC, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.actors import ActorContext
from insurance_operations.database.models.conversation import ConversationIntake
from insurance_operations.database.models.customer import Customer
from insurance_operations.database.models.lead import (
    AgencyLead,
    HandoffContactMethod,
    HandoffRequestKind,
    HandoffStatus,
    LeadHandoffRequest,
)
from insurance_operations.database.models.operations import (
    AuditActorType,
    AuditEvent,
)
from insurance_operations.database.models.telephony import (
    AgencyCallPolicy,
    AgencyInboundNumber,
    InboundCall,
    InboundCallEvent,
    InboundCallStatus,
    InboundNumberStatus,
)
from insurance_operations.errors import ApiError
from insurance_operations.telephony.schemas import (
    AvailabilityWindow,
    CallAction,
    CallPolicyInput,
    CallPolicyResponse,
    InboundCallActionResponse,
    InboundCallEventInput,
    InboundCallEventType,
    InboundCallLinkLeadInput,
    InboundCallListResponse,
    InboundCallReceiveInput,
    InboundCallResponse,
    InboundNumberCreateInput,
    InboundNumberResponse,
    InboundNumberStatusInput,
)

ACTIVE_CALL_STATUSES = {
    InboundCallStatus.RECEIVED.value,
    InboundCallStatus.CONNECTED.value,
    InboundCallStatus.TRANSFER_PENDING.value,
    InboundCallStatus.CALLBACK_PENDING.value,
}
TERMINAL_CALL_STATUSES = {
    InboundCallStatus.TRANSFERRED.value,
    InboundCallStatus.CALLBACK_REQUESTED.value,
    InboundCallStatus.COMPLETED.value,
    InboundCallStatus.FAILED.value,
}


class TelephonyService:
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_policy(self, *, actor: ActorContext) -> CallPolicyResponse:
        with self._session_factory() as session:
            policy = session.scalar(
                select(AgencyCallPolicy).where(
                    AgencyCallPolicy.agency_id == actor.agency_id
                )
            )
            if policy is None:
                raise ApiError(
                    status_code=404,
                    code="CALL_POLICY_NOT_FOUND",
                    message="The agency call policy has not been configured",
                )
            return policy_response(policy)

    def replace_policy(
        self,
        *,
        actor: ActorContext,
        request: CallPolicyInput,
        correlation_id: UUID,
    ) -> CallPolicyResponse:
        with self._session_factory() as session, session.begin():
            policy = session.scalar(
                select(AgencyCallPolicy)
                .where(AgencyCallPolicy.agency_id == actor.agency_id)
                .with_for_update()
            )
            if policy is None:
                if request.expected_row_version != 0:
                    raise version_conflict("CALL_POLICY", 0)
                policy = AgencyCallPolicy(
                    agency_id=actor.agency_id,
                    created_by=actor.app_user_id,
                    updated_by=actor.app_user_id,
                    **policy_values(request),
                )
                session.add(policy)
                event_type = "AGENCY_CALL_POLICY_CREATED"
            else:
                require_version(
                    resource="CALL_POLICY",
                    actual=policy.row_version,
                    expected=request.expected_row_version,
                )
                for field, value in policy_values(request).items():
                    setattr(policy, field, value)
                policy.updated_by = actor.app_user_id
                event_type = "AGENCY_CALL_POLICY_UPDATED"
            session.flush()
            session.refresh(policy)
            session.add(
                telephony_audit(
                    actor=actor,
                    event_type=event_type,
                    summary="Agency inbound-call policy changed",
                    details={
                        "call_policy_id": str(policy.id),
                        "row_version": policy.row_version,
                    },
                    correlation_id=correlation_id,
                )
            )
            return policy_response(policy)

    def list_numbers(self, *, actor: ActorContext) -> list[InboundNumberResponse]:
        with self._session_factory() as session:
            numbers = session.scalars(
                select(AgencyInboundNumber)
                .where(AgencyInboundNumber.agency_id == actor.agency_id)
                .order_by(
                    AgencyInboundNumber.created_at,
                    AgencyInboundNumber.id,
                )
            ).all()
            return [inbound_number_response(number) for number in numbers]

    def create_number(
        self,
        *,
        actor: ActorContext,
        request: InboundNumberCreateInput,
        correlation_id: UUID,
    ) -> InboundNumberResponse:
        number = AgencyInboundNumber(
            agency_id=actor.agency_id,
            phone_number_e164=request.phone_number_e164,
            label=request.label,
            status=request.status.value,
            created_by=actor.app_user_id,
            updated_by=actor.app_user_id,
        )
        try:
            with self._session_factory() as session, session.begin():
                session.add(number)
                session.flush()
                session.refresh(number)
                session.add(
                    telephony_audit(
                        actor=actor,
                        event_type="AGENCY_INBOUND_NUMBER_CREATED",
                        summary="Agency inbound number created",
                        details={
                            "inbound_number_id": str(number.id),
                            "status": number.status,
                        },
                        correlation_id=correlation_id,
                    )
                )
                return inbound_number_response(number)
        except IntegrityError as error:
            raise ApiError(
                status_code=409,
                code="INBOUND_NUMBER_ALREADY_EXISTS",
                message="The inbound phone number is already mapped",
            ) from error

    def set_number_status(
        self,
        *,
        actor: ActorContext,
        number_id: UUID,
        request: InboundNumberStatusInput,
        correlation_id: UUID,
    ) -> InboundNumberResponse:
        with self._session_factory() as session, session.begin():
            number = session.scalar(
                select(AgencyInboundNumber)
                .where(
                    AgencyInboundNumber.id == number_id,
                    AgencyInboundNumber.agency_id == actor.agency_id,
                )
                .with_for_update()
            )
            if number is None:
                raise ApiError(
                    status_code=404,
                    code="INBOUND_NUMBER_NOT_FOUND",
                    message="The inbound phone number was not found",
                )
            require_version(
                resource="INBOUND_NUMBER",
                actual=number.row_version,
                expected=request.expected_row_version,
            )
            number.status = request.status.value
            number.updated_by = actor.app_user_id
            session.flush()
            session.refresh(number)
            session.add(
                telephony_audit(
                    actor=actor,
                    event_type="AGENCY_INBOUND_NUMBER_STATUS_CHANGED",
                    summary="Agency inbound number status changed",
                    details={
                        "inbound_number_id": str(number.id),
                        "status": number.status,
                    },
                    correlation_id=correlation_id,
                )
            )
            return inbound_number_response(number)

    def receive_call(
        self,
        *,
        actor: ActorContext,
        request: InboundCallReceiveInput,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        return self._receive_call(
            actor=actor,
            request=request,
            correlation_id=correlation_id,
        )

    def receive_provider_call(
        self,
        *,
        request: InboundCallReceiveInput,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        return self._receive_call(
            actor=None,
            request=request,
            correlation_id=correlation_id,
        )

    def _receive_call(
        self,
        *,
        actor: ActorContext | None,
        request: InboundCallReceiveInput,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        with self._session_factory() as session, session.begin():
            existing = session.scalar(
                select(InboundCall).where(
                    InboundCall.adapter_name == request.adapter_name,
                    InboundCall.source_call_reference == request.source_call_reference,
                )
            )

            if existing is not None:
                expected_agency_id = (
                    actor.agency_id if actor is not None else existing.agency_id
                )
                validate_receive_replay(
                    session,
                    expected_agency_id,
                    request,
                    existing,
                    compare_occurred_at=actor is not None,
                )
                return replay_receive_response(existing)

            number_filters = [
                AgencyInboundNumber.phone_number_e164 == request.called_number_e164,
                AgencyInboundNumber.status == InboundNumberStatus.ACTIVE.value,
            ]

            if actor is not None:
                number_filters.append(AgencyInboundNumber.agency_id == actor.agency_id)

            number = session.scalar(select(AgencyInboundNumber).where(*number_filters))

            if number is None:
                raise ApiError(
                    status_code=404,
                    code="INBOUND_ROUTE_NOT_FOUND",
                    message="No active inbound route matches the called number",
                )

            agency_id = number.agency_id

            policy = session.scalar(
                select(AgencyCallPolicy)
                .where(AgencyCallPolicy.agency_id == agency_id)
                .with_for_update()
            )

            if policy is None or not policy.inbound_enabled:
                raise ApiError(
                    status_code=409,
                    code="INBOUND_CALLS_DISABLED",
                    message="Inbound calls are disabled for this agency",
                )

            existing = session.scalar(
                select(InboundCall).where(
                    InboundCall.adapter_name == request.adapter_name,
                    InboundCall.source_call_reference == request.source_call_reference,
                )
            )

            if existing is not None:
                validate_receive_replay(
                    session,
                    agency_id,
                    request,
                    existing,
                    compare_occurred_at=actor is not None,
                )
                return replay_receive_response(existing)

            enforce_call_limits(
                session,
                agency_id,
                policy,
                request.occurred_at,
            )

            inbound_call = InboundCall(
                agency_id=agency_id,
                inbound_number_id=number.id,
                status=InboundCallStatus.RECEIVED.value,
                caller_number_e164=request.caller_number_e164,
                adapter_name=request.adapter_name,
                source_call_reference=request.source_call_reference,
                adapter_metadata={
                    "adapter_version": request.adapter_version,
                },
                policy_snapshot=policy_snapshot(policy),
                received_at=request.occurred_at,
            )

            try:
                with session.begin_nested():
                    session.add(inbound_call)
                    session.flush()
            except IntegrityError:
                existing = session.scalar(
                    select(InboundCall).where(
                        InboundCall.adapter_name == request.adapter_name,
                        InboundCall.source_call_reference
                        == request.source_call_reference,
                    )
                )

                if existing is None:
                    raise

                validate_receive_replay(
                    session,
                    agency_id,
                    request,
                    existing,
                    compare_occurred_at=actor is not None,
                )
                return replay_receive_response(existing)

            session.refresh(inbound_call)

            session.add(
                InboundCallEvent(
                    agency_id=agency_id,
                    inbound_call_id=inbound_call.id,
                    event_key="call-received",
                    event_type="CALL_RECEIVED",
                    occurred_at=request.occurred_at,
                    details={
                        "resulting_status": inbound_call.status,
                    },
                )
            )

            if actor is None:
                audit_event = telephony_system_audit(
                    agency_id=agency_id,
                    event_type="INBOUND_CALL_RECEIVED",
                    summary="Inbound call received",
                    details={
                        "inbound_call_id": str(inbound_call.id),
                        "inbound_number_id": str(number.id),
                    },
                    correlation_id=correlation_id,
                )
            else:
                audit_event = telephony_audit(
                    actor=actor,
                    event_type="INBOUND_CALL_RECEIVED",
                    summary="Inbound call received",
                    details={
                        "inbound_call_id": str(inbound_call.id),
                        "inbound_number_id": str(number.id),
                    },
                    correlation_id=correlation_id,
                )

            session.add(audit_event)

            return call_action_response(
                inbound_call,
                action=CallAction.ANSWER_AI,
            )

    def list_calls(
        self,
        *,
        actor: ActorContext,
        status: InboundCallStatus | None,
        limit: int,
        offset: int,
    ) -> InboundCallListResponse:
        filters = [InboundCall.agency_id == actor.agency_id]
        if status is not None:
            filters.append(InboundCall.status == status.value)
        with self._session_factory() as session:
            calls = session.scalars(
                select(InboundCall)
                .where(*filters)
                .order_by(InboundCall.created_at.desc(), InboundCall.id)
                .limit(limit)
                .offset(offset)
            ).all()
            total = session.scalar(
                select(func.count()).select_from(InboundCall).where(*filters)
            )
            return InboundCallListResponse(
                items=[inbound_call_response(call) for call in calls],
                total=total or 0,
                limit=limit,
                offset=offset,
            )

    def get_call(
        self,
        *,
        actor: ActorContext,
        call_id: UUID,
    ) -> InboundCallResponse:
        with self._session_factory() as session:
            return inbound_call_response(require_owned_call(session, actor, call_id))

    def apply_event(
        self,
        *,
        actor: ActorContext,
        call_id: UUID,
        request: InboundCallEventInput,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        with self._session_factory() as session, session.begin():
            inbound_call = require_owned_call(
                session,
                actor,
                call_id,
                for_update=True,
            )
            existing_event = session.scalar(
                select(InboundCallEvent).where(
                    InboundCallEvent.inbound_call_id == inbound_call.id,
                    InboundCallEvent.event_key == request.event_key,
                )
            )
            if existing_event is not None:
                if (
                    existing_event.event_type != request.event_type.value
                    or existing_event.occurred_at != request.occurred_at
                    or existing_event.details.get("failure_code")
                    != request.failure_code
                ):
                    raise ApiError(
                        status_code=409,
                        code="INBOUND_CALL_EVENT_KEY_REUSED",
                        message="The call event key was reused with different data",
                    )
                return replay_event_response(inbound_call, existing_event)
            if request.occurred_at < inbound_call.received_at:
                raise ApiError(
                    status_code=409,
                    code="INBOUND_CALL_EVENT_TIME_INVALID",
                    message="The call event occurred before the call was received",
                )

            directive = transition_call(inbound_call, request)
            session.flush()
            session.refresh(inbound_call)
            event_details: dict[str, object] = {
                "action": directive.action.value,
                "resulting_status": inbound_call.status,
            }
            if directive.message is not None:
                event_details["message"] = directive.message
            if request.failure_code is not None:
                event_details["failure_code"] = request.failure_code
            session.add(
                InboundCallEvent(
                    agency_id=actor.agency_id,
                    inbound_call_id=inbound_call.id,
                    event_key=request.event_key,
                    event_type=request.event_type.value,
                    occurred_at=request.occurred_at,
                    details=event_details,
                )
            )
            session.add(
                telephony_audit(
                    actor=actor,
                    event_type="INBOUND_CALL_STATE_CHANGED",
                    summary="Inbound call state changed",
                    details={
                        "inbound_call_id": str(inbound_call.id),
                        "event_type": request.event_type.value,
                        "status": inbound_call.status,
                    },
                    correlation_id=correlation_id,
                )
            )
            directive.call = inbound_call_response(inbound_call)
            return directive

    def apply_provider_event(
        self,
        *,
        call_id: UUID,
        request: InboundCallEventInput,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        with self._session_factory() as session, session.begin():
            inbound_call = session.get(InboundCall, call_id, with_for_update=True)
            if inbound_call is None:
                raise ApiError(
                    status_code=404,
                    code="INBOUND_CALL_NOT_FOUND",
                    message="The inbound call was not found",
                )
            existing_event = session.scalar(
                select(InboundCallEvent).where(
                    InboundCallEvent.inbound_call_id == inbound_call.id,
                    InboundCallEvent.event_key == request.event_key,
                )
            )
            if existing_event is not None:
                if (
                    existing_event.event_type != request.event_type.value
                    or existing_event.details.get("failure_code")
                    != request.failure_code
                ):
                    raise ApiError(
                        status_code=409,
                        code="INBOUND_CALL_EVENT_KEY_REUSED",
                        message="The call event key was reused with different data",
                    )
                return replay_event_response(inbound_call, existing_event)
            if request.occurred_at < inbound_call.received_at:
                raise ApiError(
                    status_code=409,
                    code="INBOUND_CALL_EVENT_TIME_INVALID",
                    message="The call event occurred before the call was received",
                )

            directive = transition_call(inbound_call, request)
            session.flush()
            session.refresh(inbound_call)
            event_details: dict[str, object] = {
                "action": directive.action.value,
                "resulting_status": inbound_call.status,
            }
            if directive.message is not None:
                event_details["message"] = directive.message
            if request.failure_code is not None:
                event_details["failure_code"] = request.failure_code
            session.add(
                InboundCallEvent(
                    agency_id=inbound_call.agency_id,
                    inbound_call_id=inbound_call.id,
                    event_key=request.event_key,
                    event_type=request.event_type.value,
                    occurred_at=request.occurred_at,
                    details=event_details,
                )
            )
            session.add(
                telephony_system_audit(
                    agency_id=inbound_call.agency_id,
                    event_type="INBOUND_CALL_STATE_CHANGED",
                    summary="Inbound call state changed",
                    details={
                        "inbound_call_id": str(inbound_call.id),
                        "event_type": request.event_type.value,
                        "status": inbound_call.status,
                    },
                    correlation_id=correlation_id,
                )
            )
            directive.call = inbound_call_response(inbound_call)
            return directive

    def apply_provider_event_by_reference(
        self,
        *,
        adapter_name: str,
        source_call_reference: str,
        request: InboundCallEventInput,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        with self._session_factory() as session:
            call_id = session.scalar(
                select(InboundCall.id).where(
                    InboundCall.adapter_name == adapter_name,
                    InboundCall.source_call_reference == source_call_reference,
                )
            )
        if call_id is None:
            raise ApiError(
                status_code=404,
                code="INBOUND_CALL_NOT_FOUND",
                message="The inbound call was not found",
            )
        return self.apply_provider_event(
            call_id=call_id,
            request=request,
            correlation_id=correlation_id,
        )

    def link_lead(
        self,
        *,
        actor: ActorContext,
        call_id: UUID,
        request: InboundCallLinkLeadInput,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        with self._session_factory() as session, session.begin():
            inbound_call = require_owned_call(
                session,
                actor,
                call_id,
                for_update=True,
            )
            if inbound_call.lead_id is not None:
                if inbound_call.lead_id != request.lead_id:
                    raise ApiError(
                        status_code=409,
                        code="INBOUND_CALL_LEAD_CONFLICT",
                        message="The call is already linked to another lead",
                    )
                return call_action_response(
                    inbound_call,
                    action=(
                        CallAction.CALLBACK_CONFIRMED
                        if inbound_call.status
                        == InboundCallStatus.CALLBACK_REQUESTED.value
                        else CallAction.CONTINUE_AI
                    ),
                    replayed=True,
                )
            require_version(
                resource="INBOUND_CALL",
                actual=inbound_call.row_version,
                expected=request.expected_row_version,
            )
            row = session.execute(
                select(AgencyLead, Customer, ConversationIntake)
                .join(Customer, Customer.id == AgencyLead.customer_id)
                .join(
                    ConversationIntake,
                    ConversationIntake.id == AgencyLead.conversation_intake_id,
                )
                .where(
                    AgencyLead.id == request.lead_id,
                    AgencyLead.agency_id == actor.agency_id,
                )
            ).one_or_none()
            if row is None:
                raise ApiError(
                    status_code=404,
                    code="LEAD_NOT_FOUND",
                    message="The lead was not found",
                )
            lead, customer, intake = row
            inbound_call.lead_id = lead.id
            action = CallAction.CONTINUE_AI
            if inbound_call.status == InboundCallStatus.CALLBACK_PENDING.value:
                contact_method = callback_contact_method(customer)
                handoff = LeadHandoffRequest(
                    agency_id=actor.agency_id,
                    lead_id=lead.id,
                    conversation_session_id=intake.conversation_session_id,
                    inbound_call_id=inbound_call.id,
                    request_kind=HandoffRequestKind.CALLBACK.value,
                    preferred_contact_method=contact_method.value,
                    reason="Inbound call transfer was unavailable; callback requested.",
                    availability=None,
                    transfer_attempted=False,
                    status=HandoffStatus.REQUESTED.value,
                    created_by=actor.app_user_id,
                    updated_by=actor.app_user_id,
                )
                session.add(handoff)
                inbound_call.status = InboundCallStatus.CALLBACK_REQUESTED.value
                action = CallAction.CALLBACK_CONFIRMED
            elif inbound_call.status not in {
                InboundCallStatus.CONNECTED.value,
                InboundCallStatus.RECEIVED.value,
            }:
                raise invalid_call_transition(inbound_call.status, "LEAD_LINKED")
            session.flush()
            session.refresh(inbound_call)
            session.add(
                InboundCallEvent(
                    agency_id=actor.agency_id,
                    inbound_call_id=inbound_call.id,
                    event_key=f"lead-linked:{lead.id}",
                    event_type="LEAD_LINKED",
                    occurred_at=datetime.now(UTC),
                    details={
                        "action": action.value,
                        "lead_id": str(lead.id),
                        "resulting_status": inbound_call.status,
                    },
                )
            )
            session.add(
                telephony_audit(
                    actor=actor,
                    event_type="INBOUND_CALL_LEAD_LINKED",
                    summary="Inbound call linked to lead",
                    details={
                        "inbound_call_id": str(inbound_call.id),
                        "lead_id": str(lead.id),
                        "status": inbound_call.status,
                    },
                    correlation_id=correlation_id,
                    customer_id=customer.id,
                )
            )
            return call_action_response(inbound_call, action=action)


def transition_call(
    inbound_call: InboundCall,
    request: InboundCallEventInput,
) -> InboundCallActionResponse:
    current = inbound_call.status
    event = request.event_type
    if event is InboundCallEventType.ANSWERED:
        require_call_status(current, event, {InboundCallStatus.RECEIVED.value})
        inbound_call.status = InboundCallStatus.CONNECTED.value
        inbound_call.answered_at = request.occurred_at
        return call_action_response(inbound_call, action=CallAction.CONTINUE_AI)
    if event is InboundCallEventType.TRANSFER_REQUESTED:
        require_call_status(current, event, {InboundCallStatus.CONNECTED.value})
        available = is_staff_available(
            inbound_call.policy_snapshot, request.occurred_at
        )
        if (
            snapshot_bool(inbound_call.policy_snapshot, "transfer_enabled")
            and available
        ):
            inbound_call.status = InboundCallStatus.TRANSFER_PENDING.value
            return call_action_response(
                inbound_call,
                action=CallAction.TRANSFER,
                transfer_destination_e164=snapshot_string(
                    inbound_call.policy_snapshot,
                    "transfer_destination_e164",
                ),
                transfer_ring_timeout_seconds=snapshot_int(
                    inbound_call.policy_snapshot,
                    "transfer_ring_timeout_seconds",
                ),
            )
        message_key = "unavailable_message" if available else "after_hours_message"
        message = snapshot_string(inbound_call.policy_snapshot, message_key)
        if snapshot_bool(
            inbound_call.policy_snapshot,
            "callback_fallback_enabled",
        ):
            inbound_call.status = InboundCallStatus.CALLBACK_PENDING.value
            return call_action_response(
                inbound_call,
                action=CallAction.COLLECT_CALLBACK,
                message=message,
            )
        return call_action_response(
            inbound_call,
            action=CallAction.CONTINUE_AI,
            message=message,
        )
    if event is InboundCallEventType.CALLBACK_REQUESTED:
        require_call_status(current, event, {InboundCallStatus.CONNECTED.value})
        if snapshot_bool(
            inbound_call.policy_snapshot,
            "callback_fallback_enabled",
        ):
            inbound_call.status = InboundCallStatus.CALLBACK_PENDING.value
            return call_action_response(
                inbound_call,
                action=CallAction.COLLECT_CALLBACK,
                message=snapshot_string(
                    inbound_call.policy_snapshot,
                    "unavailable_message",
                ),
            )
        return call_action_response(
            inbound_call,
            action=CallAction.CONTINUE_AI,
            message=snapshot_string(
                inbound_call.policy_snapshot,
                "unavailable_message",
            ),
        )
    if event is InboundCallEventType.TRANSFER_SUCCEEDED:
        require_call_status(
            current,
            event,
            {InboundCallStatus.TRANSFER_PENDING.value},
        )
        inbound_call.status = InboundCallStatus.TRANSFERRED.value
        inbound_call.ended_at = request.occurred_at
        return call_action_response(inbound_call, action=CallAction.END)
    if event is InboundCallEventType.TRANSFER_FAILED:
        require_call_status(
            current,
            event,
            {InboundCallStatus.TRANSFER_PENDING.value},
        )
        if snapshot_bool(
            inbound_call.policy_snapshot,
            "callback_fallback_enabled",
        ):
            inbound_call.status = InboundCallStatus.CALLBACK_PENDING.value
            return call_action_response(
                inbound_call,
                action=CallAction.COLLECT_CALLBACK,
                message=snapshot_string(
                    inbound_call.policy_snapshot,
                    "unavailable_message",
                ),
            )
        inbound_call.status = InboundCallStatus.CONNECTED.value
        return call_action_response(
            inbound_call,
            action=CallAction.CONTINUE_AI,
            message=snapshot_string(
                inbound_call.policy_snapshot,
                "unavailable_message",
            ),
        )
    if event is InboundCallEventType.CALL_ENDED:
        require_call_status(
            current,
            event,
            {
                InboundCallStatus.RECEIVED.value,
                InboundCallStatus.CONNECTED.value,
                InboundCallStatus.CALLBACK_PENDING.value,
                InboundCallStatus.CALLBACK_REQUESTED.value,
            },
        )
        inbound_call.ended_at = request.occurred_at
        if current == InboundCallStatus.CALLBACK_PENDING.value:
            inbound_call.status = InboundCallStatus.FAILED.value
            inbound_call.failure_code = "CALLBACK_NOT_CAPTURED"
        elif current != InboundCallStatus.CALLBACK_REQUESTED.value:
            inbound_call.status = InboundCallStatus.COMPLETED.value
        return call_action_response(inbound_call, action=CallAction.END)
    if event is InboundCallEventType.PROVIDER_FAILED:
        if current in TERMINAL_CALL_STATUSES:
            raise invalid_call_transition(current, event.value)
        inbound_call.status = InboundCallStatus.FAILED.value
        inbound_call.failure_code = request.failure_code or "PROVIDER_FAILED"
        inbound_call.ended_at = request.occurred_at
        return call_action_response(inbound_call, action=CallAction.END)
    raise invalid_call_transition(current, event.value)


def enforce_call_limits(
    session: Session,
    agency_id: UUID,
    policy: AgencyCallPolicy,
    occurred_at: datetime,
) -> None:
    active_count = session.scalar(
        select(func.count())
        .select_from(InboundCall)
        .where(
            InboundCall.agency_id == agency_id,
            InboundCall.status.in_(ACTIVE_CALL_STATUSES),
        )
    )
    if (active_count or 0) >= policy.max_concurrent_calls:
        raise ApiError(
            status_code=429,
            code="INBOUND_CALL_CONCURRENCY_LIMIT_REACHED",
            message="The agency inbound-call concurrency limit was reached",
        )
    utc_time = occurred_at.astimezone(UTC)
    day_start = datetime.combine(utc_time.date(), time.min, tzinfo=UTC)
    daily_count = session.scalar(
        select(func.count())
        .select_from(InboundCall)
        .where(
            InboundCall.agency_id == agency_id,
            InboundCall.received_at >= day_start,
        )
    )
    if (daily_count or 0) >= policy.daily_call_limit:
        raise ApiError(
            status_code=429,
            code="INBOUND_CALL_DAILY_LIMIT_REACHED",
            message="The agency daily inbound-call limit was reached",
        )


def is_staff_available(snapshot: dict[str, object], occurred_at: datetime) -> bool:
    local_time = occurred_at.astimezone(ZoneInfo(snapshot_string(snapshot, "timezone")))
    windows = snapshot["availability_windows"]
    if not isinstance(windows, list):
        return False
    for raw_window in windows:
        if not isinstance(raw_window, dict):
            continue
        if raw_window.get("weekday") != local_time.weekday():
            continue
        start_value = raw_window.get("start_local")
        end_value = raw_window.get("end_local")
        if not isinstance(start_value, str) or not isinstance(end_value, str):
            continue
        start_local = time.fromisoformat(start_value)
        end_local = time.fromisoformat(end_value)
        if start_local <= local_time.time().replace(tzinfo=None) < end_local:
            return True
    return False


def policy_values(request: CallPolicyInput) -> dict[str, object]:
    return {
        "inbound_enabled": request.inbound_enabled,
        "timezone": request.timezone,
        "availability_windows": [
            {
                "weekday": window.weekday,
                "start_local": window.start_local.isoformat(timespec="minutes"),
                "end_local": window.end_local.isoformat(timespec="minutes"),
            }
            for window in request.availability_windows
        ],
        "transfer_enabled": request.transfer_enabled,
        "transfer_destination_e164": request.transfer_destination_e164,
        "transfer_ring_timeout_seconds": request.transfer_ring_timeout_seconds,
        "max_concurrent_calls": request.max_concurrent_calls,
        "daily_call_limit": request.daily_call_limit,
        "callback_fallback_enabled": request.callback_fallback_enabled,
        "after_hours_message": request.after_hours_message,
        "unavailable_message": request.unavailable_message,
    }


def policy_snapshot(policy: AgencyCallPolicy) -> dict[str, object]:
    return {
        "policy_id": str(policy.id),
        "policy_row_version": policy.row_version,
        "timezone": policy.timezone,
        "availability_windows": policy.availability_windows,
        "transfer_enabled": policy.transfer_enabled,
        "transfer_destination_e164": policy.transfer_destination_e164,
        "transfer_ring_timeout_seconds": policy.transfer_ring_timeout_seconds,
        "callback_fallback_enabled": policy.callback_fallback_enabled,
        "after_hours_message": policy.after_hours_message,
        "unavailable_message": policy.unavailable_message,
    }


def policy_response(policy: AgencyCallPolicy) -> CallPolicyResponse:
    return CallPolicyResponse(
        id=policy.id,
        agency_id=policy.agency_id,
        inbound_enabled=policy.inbound_enabled,
        timezone=policy.timezone,
        availability_windows=[
            AvailabilityWindow.model_validate(window)
            for window in policy.availability_windows
        ],
        transfer_enabled=policy.transfer_enabled,
        transfer_destination_e164=policy.transfer_destination_e164,
        transfer_ring_timeout_seconds=policy.transfer_ring_timeout_seconds,
        max_concurrent_calls=policy.max_concurrent_calls,
        daily_call_limit=policy.daily_call_limit,
        callback_fallback_enabled=policy.callback_fallback_enabled,
        after_hours_message=policy.after_hours_message,
        unavailable_message=policy.unavailable_message,
        row_version=policy.row_version,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def inbound_number_response(number: AgencyInboundNumber) -> InboundNumberResponse:
    return InboundNumberResponse(
        id=number.id,
        agency_id=number.agency_id,
        phone_number_e164=number.phone_number_e164,
        label=number.label,
        status=InboundNumberStatus(number.status),
        row_version=number.row_version,
        created_at=number.created_at,
        updated_at=number.updated_at,
    )


def inbound_call_response(inbound_call: InboundCall) -> InboundCallResponse:
    return InboundCallResponse(
        id=inbound_call.id,
        agency_id=inbound_call.agency_id,
        inbound_number_id=inbound_call.inbound_number_id,
        lead_id=inbound_call.lead_id,
        status=InboundCallStatus(inbound_call.status),
        caller_number_e164=inbound_call.caller_number_e164,
        adapter_name=inbound_call.adapter_name,
        received_at=inbound_call.received_at,
        answered_at=inbound_call.answered_at,
        ended_at=inbound_call.ended_at,
        failure_code=inbound_call.failure_code,
        row_version=inbound_call.row_version,
        created_at=inbound_call.created_at,
        updated_at=inbound_call.updated_at,
    )


def call_action_response(
    inbound_call: InboundCall,
    *,
    action: CallAction,
    message: str | None = None,
    transfer_destination_e164: str | None = None,
    transfer_ring_timeout_seconds: int | None = None,
    replayed: bool = False,
) -> InboundCallActionResponse:
    return InboundCallActionResponse(
        call=inbound_call_response(inbound_call),
        action=action,
        message=message,
        transfer_destination_e164=transfer_destination_e164,
        transfer_ring_timeout_seconds=transfer_ring_timeout_seconds,
        replayed=replayed,
    )


def replay_event_response(
    inbound_call: InboundCall,
    event: InboundCallEvent,
) -> InboundCallActionResponse:
    action_value = event.details.get("action")
    if not isinstance(action_value, str):
        action_value = CallAction.CONTINUE_AI.value
    action = CallAction(action_value)
    return call_action_response(
        inbound_call,
        action=action,
        message=(
            str(event.details["message"])
            if event.details.get("message") is not None
            else None
        ),
        transfer_destination_e164=(
            snapshot_string(
                inbound_call.policy_snapshot,
                "transfer_destination_e164",
            )
            if action is CallAction.TRANSFER
            else None
        ),
        transfer_ring_timeout_seconds=(
            snapshot_int(
                inbound_call.policy_snapshot,
                "transfer_ring_timeout_seconds",
            )
            if action is CallAction.TRANSFER
            else None
        ),
        replayed=True,
    )


def replay_receive_response(inbound_call: InboundCall) -> InboundCallActionResponse:
    if inbound_call.status == InboundCallStatus.RECEIVED.value:
        action = CallAction.ANSWER_AI
    elif inbound_call.status == InboundCallStatus.CONNECTED.value:
        action = CallAction.CONTINUE_AI
    elif inbound_call.status == InboundCallStatus.TRANSFER_PENDING.value:
        return call_action_response(
            inbound_call,
            action=CallAction.TRANSFER,
            transfer_destination_e164=snapshot_string(
                inbound_call.policy_snapshot,
                "transfer_destination_e164",
            ),
            transfer_ring_timeout_seconds=snapshot_int(
                inbound_call.policy_snapshot,
                "transfer_ring_timeout_seconds",
            ),
            replayed=True,
        )
    elif inbound_call.status == InboundCallStatus.CALLBACK_PENDING.value:
        action = CallAction.COLLECT_CALLBACK
    elif inbound_call.status == InboundCallStatus.CALLBACK_REQUESTED.value:
        action = CallAction.CALLBACK_CONFIRMED
    else:
        action = CallAction.END
    return call_action_response(inbound_call, action=action, replayed=True)


def callback_contact_method(customer: Customer) -> HandoffContactMethod:
    if customer.phone is not None:
        return HandoffContactMethod.PHONE
    if customer.email is not None:
        return HandoffContactMethod.EMAIL
    return HandoffContactMethod.NO_PREFERENCE


def validate_receive_replay(
    session: Session,
    expected_agency_id: UUID,
    request: InboundCallReceiveInput,
    inbound_call: InboundCall,
    *,
    compare_occurred_at: bool,
) -> None:
    number = session.get(
        AgencyInboundNumber,
        inbound_call.inbound_number_id,
    )
    adapter_version = inbound_call.adapter_metadata.get("adapter_version")

    replay_mismatch = (
        inbound_call.agency_id != expected_agency_id
        or inbound_call.caller_number_e164 != request.caller_number_e164
        or number is None
        or number.phone_number_e164 != request.called_number_e164
        or adapter_version != request.adapter_version
    )

    if compare_occurred_at and inbound_call.received_at != request.occurred_at:
        replay_mismatch = True

    if replay_mismatch:
        raise ApiError(
            status_code=409,
            code="INBOUND_CALL_REFERENCE_REUSED",
            message="The source call reference was reused",
        )


def snapshot_bool(snapshot: dict[str, object], key: str) -> bool:
    value = snapshot.get(key)
    if not isinstance(value, bool):
        raise RuntimeError(f"Inbound-call policy snapshot has invalid {key}")
    return value


def snapshot_int(snapshot: dict[str, object], key: str) -> int:
    value = snapshot.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeError(f"Inbound-call policy snapshot has invalid {key}")
    return value


def snapshot_string(snapshot: dict[str, object], key: str) -> str:
    value = snapshot.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Inbound-call policy snapshot has invalid {key}")
    return value


def require_owned_call(
    session: Session,
    actor: ActorContext,
    call_id: UUID,
    *,
    for_update: bool = False,
) -> InboundCall:
    statement = select(InboundCall).where(
        InboundCall.id == call_id,
        InboundCall.agency_id == actor.agency_id,
    )
    if for_update:
        statement = statement.with_for_update()
    inbound_call = session.scalar(statement)
    if inbound_call is None:
        raise ApiError(
            status_code=404,
            code="INBOUND_CALL_NOT_FOUND",
            message="The inbound call was not found",
        )
    return inbound_call


def require_call_status(
    current: str,
    event: InboundCallEventType,
    allowed: set[str],
) -> None:
    if current not in allowed:
        raise invalid_call_transition(current, event.value)


def invalid_call_transition(current: str, event: str) -> ApiError:
    return ApiError(
        status_code=409,
        code="INBOUND_CALL_STATE_TRANSITION_INVALID",
        message="The call event is not allowed in the current state",
        details={"current_status": current, "event_type": event},
    )


def require_version(*, resource: str, actual: int, expected: int) -> None:
    if actual != expected:
        raise version_conflict(resource, actual)


def version_conflict(resource: str, current: int) -> ApiError:
    return ApiError(
        status_code=409,
        code=f"{resource}_VERSION_CONFLICT",
        message="The resource was changed by another request",
        details={"current_row_version": current},
    )


def telephony_system_audit(
    *,
    agency_id: UUID,
    event_type: str,
    summary: str,
    details: dict[str, object],
    correlation_id: UUID,
) -> AuditEvent:
    return AuditEvent(
        agency_id=agency_id,
        actor_type=AuditActorType.SYSTEM.value,
        actor_user_id=None,
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        summary=summary,
        details=details,
        correlation_id=correlation_id,
        event_version=1,
    )


def telephony_audit(
    *,
    actor: ActorContext,
    event_type: str,
    summary: str,
    details: dict[str, object],
    correlation_id: UUID,
    customer_id: UUID | None = None,
) -> AuditEvent:
    return AuditEvent(
        agency_id=actor.agency_id,
        actor_type=AuditActorType.STAFF.value,
        actor_user_id=actor.app_user_id,
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        customer_id=customer_id,
        summary=summary,
        details=details,
        correlation_id=correlation_id,
        event_version=1,
    )
