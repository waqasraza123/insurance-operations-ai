import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.actors import (
    ActorContext,
    ActorResolutionError,
    resolve_development_actor,
)
from insurance_operations.approved_faqs.service import ApprovedFaqService
from insurance_operations.conversations.schemas import ConversationTurn
from insurance_operations.customers import CustomerInput, customer_from_input
from insurance_operations.database.models.conversation import (
    ConversationChannel,
    ConversationIntake,
    ConversationIntakeConfirmationReceipt,
    ConversationSession,
    ConversationSessionStatus,
)
from insurance_operations.database.models.lead import (
    AgencyLead,
    HandoffContactMethod,
    HandoffRequestKind,
    HandoffStatus,
    LeadHandoffRequest,
    LeadStatus,
)
from insurance_operations.database.models.operations import (
    AuditActorType,
    AuditEvent,
)
from insurance_operations.database.models.telephony import (
    InboundCall,
    InboundCallEvent,
    InboundCallStatus,
)
from insurance_operations.errors import ApiError
from insurance_operations.telephony.contracts import (
    TelephonyAdapter,
    TelephonyAdapterError,
    TransferInstruction,
    VerifiedTransferResult,
)
from insurance_operations.telephony.phone_schemas import (
    NormalizedPostCall,
    PhoneCallContext,
    PhoneConsentInput,
    PhoneConsentResponse,
    PhoneFaqLookupInput,
    PhoneFaqLookupResponse,
    PhoneHandoffInput,
    PhoneHandoffKind,
    PhoneHandoffResponse,
    PhoneIntakeConfirmationInput,
    PhoneIntakeConfirmationResponse,
)
from insurance_operations.telephony.schemas import (
    CallAction,
    InboundCallEventInput,
    InboundCallEventType,
)
from insurance_operations.telephony.service import TelephonyService


class PhoneReceptionistService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        telephony_service: TelephonyService,
        telephony_adapter: TelephonyAdapter,
        development_actor_user_id: UUID,
        maximum_duration_seconds: int,
        confirmation_window_minutes: int,
    ) -> None:
        self._session_factory = session_factory
        self._telephony_service = telephony_service
        self._telephony_adapter = telephony_adapter
        self._development_actor_user_id = development_actor_user_id
        self._maximum_duration_seconds = maximum_duration_seconds
        self._confirmation_window_minutes = confirmation_window_minutes
        self._faq_service = ApprovedFaqService(session_factory=session_factory)

    def accept_consent(
        self,
        *,
        request: PhoneConsentInput,
        correlation_id: UUID,
    ) -> PhoneConsentResponse:
        now = datetime.now(UTC)
        with self._session_factory() as session, session.begin():
            actor = self._resolve_actor(session)
            inbound_call = require_phone_call(
                session,
                request.inbound_call_id,
                for_update=True,
            )
            if inbound_call.agency_id != actor.agency_id:
                raise phone_context_error()

            existing = session.scalar(
                select(ConversationSession).where(
                    ConversationSession.inbound_call_id == inbound_call.id
                )
            )
            if existing is not None:
                require_conversation_reference(existing, request.conversation_id)
                authorized_at = existing.authorized_at
                if authorized_at is None:
                    raise phone_context_error()
                response = PhoneConsentResponse(
                    conversation_session_id=existing.id,
                    accepted=True,
                    maximum_duration_seconds=existing.maximum_duration_seconds,
                )
            else:
                if inbound_call.status != InboundCallStatus.RECEIVED.value:
                    raise phone_context_error()
                conversation_session = ConversationSession(
                    agency_id=inbound_call.agency_id,
                    initiated_by=actor.app_user_id,
                    channel=ConversationChannel.PHONE.value,
                    inbound_call_id=inbound_call.id,
                    status=ConversationSessionStatus.AUTHORIZED.value,
                    provider_metadata={
                        "adapter": "elevenlabs_agents_phone",
                        "adapter_version": "1",
                        "external_session_reference": request.conversation_id,
                    },
                    disclosure_accepted_at=now,
                    microphone_consent_at=now,
                    synthetic_data_acknowledged_at=now,
                    maximum_duration_seconds=self._maximum_duration_seconds,
                    authorization_expires_at=(
                        now + timedelta(seconds=self._maximum_duration_seconds)
                    ),
                    confirmation_expires_at=(
                        now + timedelta(minutes=self._confirmation_window_minutes)
                    ),
                    authorized_at=now,
                )
                session.add(conversation_session)
                session.flush()
                session.add(
                    system_audit(
                        agency_id=inbound_call.agency_id,
                        event_type="PHONE_CONVERSATION_CONSENT_ACCEPTED",
                        summary="Phone conversation consent accepted",
                        details={
                            "inbound_call_id": str(inbound_call.id),
                            "conversation_session_id": str(conversation_session.id),
                        },
                        correlation_id=correlation_id,
                    )
                )
                authorized_at = now
                response = PhoneConsentResponse(
                    conversation_session_id=conversation_session.id,
                    accepted=True,
                    maximum_duration_seconds=self._maximum_duration_seconds,
                )

        self._telephony_service.apply_provider_event(
            call_id=request.inbound_call_id,
            request=InboundCallEventInput(
                event_key=bounded_event_key(
                    "phone-consent",
                    request.conversation_id,
                ),
                event_type=InboundCallEventType.ANSWERED,
                occurred_at=authorized_at,
            ),
            correlation_id=correlation_id,
        )
        return response

    def lookup_faq(
        self,
        *,
        request: PhoneFaqLookupInput,
        correlation_id: UUID,
    ) -> PhoneFaqLookupResponse:
        result = self._faq_service.phone_conversation_lookup(
            inbound_call_id=request.inbound_call_id,
            conversation_id=request.conversation_id,
            query=request.query,
            correlation_id=correlation_id,
        )
        return PhoneFaqLookupResponse.model_validate(result.model_dump())

    def confirm_intake(
        self,
        *,
        request: PhoneIntakeConfirmationInput,
        correlation_id: UUID,
    ) -> PhoneIntakeConfirmationResponse:
        now = datetime.now(UTC)
        fingerprint = confirmation_fingerprint(request)
        with self._session_factory() as session, session.begin():
            conversation_session = require_phone_session_context(
                session,
                request,
                for_update=True,
            )
            existing = session.scalar(
                select(ConversationIntakeConfirmationReceipt).where(
                    ConversationIntakeConfirmationReceipt.conversation_session_id
                    == conversation_session.id
                )
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ApiError(
                        status_code=409,
                        code="PHONE_CONFIRMATION_CONFLICT",
                        message="The phone intake was already confirmed differently",
                    )
                return PhoneIntakeConfirmationResponse(
                    conversation_session_id=conversation_session.id,
                    confirmation_recorded=True,
                    replayed=True,
                )
            if (
                conversation_session.status
                != ConversationSessionStatus.AUTHORIZED.value
                or conversation_session.authorization_expires_at <= now
            ):
                raise phone_context_error()

            email = (
                str(request.customer.email)
                if request.customer.email is not None
                else None
            )
            receipt = ConversationIntakeConfirmationReceipt(
                agency_id=conversation_session.agency_id,
                conversation_session_id=conversation_session.id,
                inbound_call_id=request.inbound_call_id,
                full_name=request.customer.full_name,
                email=email,
                phone=request.customer.phone,
                intake_intent=request.intake_intent,
                urgency=request.urgency.value,
                request_fingerprint=fingerprint,
                confirmed_at=now,
            )
            session.add(receipt)
            conversation_session.status = ConversationSessionStatus.REVIEW_PENDING.value
            session.add(
                system_audit(
                    agency_id=conversation_session.agency_id,
                    event_type="PHONE_INTAKE_VERBALLY_CONFIRMED",
                    summary="Phone intake verbally confirmed",
                    details={
                        "inbound_call_id": str(request.inbound_call_id),
                        "conversation_session_id": str(conversation_session.id),
                    },
                    correlation_id=correlation_id,
                )
            )
            return PhoneIntakeConfirmationResponse(
                conversation_session_id=conversation_session.id,
                confirmation_recorded=True,
            )

    def request_handoff(
        self,
        *,
        request: PhoneHandoffInput,
        correlation_id: UUID,
    ) -> PhoneHandoffResponse:
        with self._session_factory() as session:
            require_phone_session_context(session, request)

        event_type = (
            InboundCallEventType.TRANSFER_REQUESTED
            if request.kind is PhoneHandoffKind.LIVE_TRANSFER
            else InboundCallEventType.CALLBACK_REQUESTED
        )
        directive = self._telephony_service.apply_provider_event(
            call_id=request.inbound_call_id,
            request=InboundCallEventInput(
                event_key=bounded_event_key(
                    "phone-handoff",
                    request.conversation_id,
                    request.kind.value,
                ),
                event_type=event_type,
                occurred_at=datetime.now(UTC),
            ),
            correlation_id=correlation_id,
        )

        if directive.action is CallAction.TRANSFER and not directive.replayed:
            destination = directive.transfer_destination_e164
            timeout = directive.transfer_ring_timeout_seconds
            if destination is None or timeout is None:
                raise RuntimeError("transfer directive is incomplete")
            try:
                self._telephony_adapter.request_transfer(
                    source_call_reference=self._source_call_reference(
                        request.inbound_call_id
                    ),
                    instruction=TransferInstruction(
                        destination_e164=destination,
                        ring_timeout_seconds=timeout,
                    ),
                )
            except TelephonyAdapterError:
                directive = self._telephony_service.apply_provider_event(
                    call_id=request.inbound_call_id,
                    request=InboundCallEventInput(
                        event_key=bounded_event_key(
                            "transfer-command-failed",
                            request.conversation_id,
                        ),
                        event_type=InboundCallEventType.TRANSFER_FAILED,
                        occurred_at=datetime.now(UTC),
                        failure_code="TRANSFER_COMMAND_FAILED",
                    ),
                    correlation_id=correlation_id,
                )

        return PhoneHandoffResponse(
            action=directive.action,
            message=directive.message,
            replayed=directive.replayed,
        )

    def apply_transfer_result(
        self,
        *,
        result: VerifiedTransferResult,
        correlation_id: UUID,
    ) -> PhoneHandoffResponse:
        directive = self._telephony_service.apply_provider_event_by_reference(
            adapter_name=result.adapter_name,
            source_call_reference=result.source_call_reference,
            request=InboundCallEventInput(
                event_key=result.event_key,
                event_type=(
                    InboundCallEventType.TRANSFER_SUCCEEDED
                    if result.succeeded
                    else InboundCallEventType.TRANSFER_FAILED
                ),
                occurred_at=result.occurred_at,
                failure_code=result.failure_code,
            ),
            correlation_id=correlation_id,
        )
        self._reconcile_materialized_transfer(
            result=result,
            correlation_id=correlation_id,
        )
        return PhoneHandoffResponse(
            action=directive.action,
            message=directive.message,
            replayed=directive.replayed,
        )

    def _reconcile_materialized_transfer(
        self,
        *,
        result: VerifiedTransferResult,
        correlation_id: UUID,
    ) -> None:
        with self._session_factory() as session, session.begin():
            inbound_call = session.scalar(
                select(InboundCall).where(
                    InboundCall.adapter_name == result.adapter_name,
                    InboundCall.source_call_reference == result.source_call_reference,
                )
            )
            if inbound_call is None:
                raise phone_context_error()
            handoff = session.scalar(
                select(LeadHandoffRequest)
                .where(LeadHandoffRequest.inbound_call_id == inbound_call.id)
                .with_for_update()
            )
            if handoff is None:
                return

            desired_kind = (
                HandoffRequestKind.LIVE_TRANSFER.value
                if result.succeeded
                else HandoffRequestKind.CALLBACK.value
            )
            desired_status = (
                HandoffStatus.COMPLETED.value
                if result.succeeded
                else HandoffStatus.REQUESTED.value
            )
            desired_completed_at = result.occurred_at if result.succeeded else None
            if (
                handoff.request_kind == desired_kind
                and handoff.status == desired_status
                and handoff.completed_at == desired_completed_at
                and handoff.transfer_attempted
            ):
                return

            actor = self._resolve_actor(session)
            if actor.agency_id != inbound_call.agency_id:
                raise phone_context_error()
            handoff.request_kind = desired_kind
            handoff.reason = (
                "Caller completed a live transfer during the inbound call."
                if result.succeeded
                else "The live transfer failed; the caller requested follow-up."
            )
            handoff.transfer_attempted = True
            handoff.status = desired_status
            handoff.completed_at = desired_completed_at
            handoff.cancelled_at = None
            handoff.updated_by = actor.app_user_id
            session.add(
                system_audit(
                    agency_id=inbound_call.agency_id,
                    event_type="PHONE_HANDOFF_RECONCILED",
                    summary="Phone handoff reconciled with transfer result",
                    details={
                        "inbound_call_id": str(inbound_call.id),
                        "handoff_request_id": str(handoff.id),
                        "request_kind": desired_kind,
                        "status": desired_status,
                    },
                    correlation_id=correlation_id,
                )
            )

    def finalize_post_call(
        self,
        *,
        payload: dict[str, object],
        correlation_id: UUID,
    ) -> None:
        normalized = normalize_post_call(payload)
        fingerprint = post_call_fingerprint(normalized)
        occurred_at = datetime.fromtimestamp(normalized.event_timestamp, tz=UTC)

        with self._session_factory() as session, session.begin():
            inbound_call = resolve_post_call(
                session,
                normalized,
                for_update=True,
            )
            conversation_session = session.scalar(
                select(ConversationSession)
                .where(
                    ConversationSession.inbound_call_id == inbound_call.id,
                    ConversationSession.channel == ConversationChannel.PHONE.value,
                )
                .with_for_update()
            )
            event_key = bounded_event_key(
                "phone-post-call",
                normalized.event_type,
                normalized.conversation_id,
            )
            existing_event = session.scalar(
                select(InboundCallEvent).where(
                    InboundCallEvent.inbound_call_id == inbound_call.id,
                    InboundCallEvent.event_key == event_key,
                )
            )
            if existing_event is not None:
                if existing_event.details.get("fingerprint") != fingerprint:
                    raise ApiError(
                        status_code=409,
                        code="PHONE_POST_CALL_EVENT_CONFLICT",
                        message="The post-call event was replayed differently",
                    )
                return

            if normalized.event_type == "call_initiation_failure":
                self._record_initiation_failure(
                    session=session,
                    inbound_call=inbound_call,
                    conversation_session=conversation_session,
                    event_key=event_key,
                    fingerprint=fingerprint,
                    occurred_at=occurred_at,
                    correlation_id=correlation_id,
                )
                return

            if conversation_session is None:
                self._record_unconfirmed_end(
                    session=session,
                    inbound_call=inbound_call,
                    event_key=event_key,
                    fingerprint=fingerprint,
                    occurred_at=occurred_at,
                    correlation_id=correlation_id,
                )
                return
            require_conversation_reference(
                conversation_session,
                normalized.conversation_id,
            )
            receipt = session.scalar(
                select(ConversationIntakeConfirmationReceipt).where(
                    ConversationIntakeConfirmationReceipt.conversation_session_id
                    == conversation_session.id
                )
            )
            if receipt is None:
                self._record_unconfirmed_end(
                    session=session,
                    inbound_call=inbound_call,
                    event_key=event_key,
                    fingerprint=fingerprint,
                    occurred_at=occurred_at,
                    correlation_id=correlation_id,
                    conversation_session=conversation_session,
                )
                return

            self._materialize_confirmed_intake(
                session=session,
                inbound_call=inbound_call,
                conversation_session=conversation_session,
                receipt=receipt,
                normalized=normalized,
                event_key=event_key,
                fingerprint=fingerprint,
                occurred_at=occurred_at,
                correlation_id=correlation_id,
            )

    def _materialize_confirmed_intake(
        self,
        *,
        session: Session,
        inbound_call: InboundCall,
        conversation_session: ConversationSession,
        receipt: ConversationIntakeConfirmationReceipt,
        normalized: NormalizedPostCall,
        event_key: str,
        fingerprint: str,
        occurred_at: datetime,
        correlation_id: UUID,
    ) -> None:
        existing_intake = session.scalar(
            select(ConversationIntake).where(
                ConversationIntake.conversation_session_id == conversation_session.id
            )
        )
        if existing_intake is not None:
            raise ApiError(
                status_code=409,
                code="PHONE_INTAKE_ALREADY_FINALIZED",
                message="The phone intake was already finalized",
            )

        actor = self._resolve_actor(session)
        if actor.agency_id != inbound_call.agency_id:
            raise phone_context_error()
        customer_input = CustomerInput(
            full_name=receipt.full_name,
            email=receipt.email,
            phone=receipt.phone,
        )
        customer = customer_from_input(customer_input, actor)
        session.add(customer)
        session.flush()

        intake = ConversationIntake(
            agency_id=inbound_call.agency_id,
            customer_id=customer.id,
            conversation_session_id=conversation_session.id,
            created_by=actor.app_user_id,
            intake_intent=receipt.intake_intent,
            confirmed_transcript=[
                turn.model_dump(mode="json") for turn in normalized.transcript
            ],
            confirmed_at=receipt.confirmed_at,
        )
        session.add(intake)
        session.flush()
        lead = AgencyLead(
            agency_id=inbound_call.agency_id,
            customer_id=customer.id,
            conversation_intake_id=intake.id,
            status=LeadStatus.NEW.value,
            urgency=receipt.urgency,
            summary=receipt.intake_intent,
            created_by=actor.app_user_id,
            updated_by=actor.app_user_id,
        )
        session.add(lead)
        session.flush()
        inbound_call.lead_id = lead.id

        handoff_kind = requested_handoff_kind(session, inbound_call.id)
        if handoff_kind is not None:
            completed_transfer = successful_transfer_event(
                session,
                inbound_call.id,
            )
            session.add(
                LeadHandoffRequest(
                    agency_id=inbound_call.agency_id,
                    lead_id=lead.id,
                    conversation_session_id=conversation_session.id,
                    inbound_call_id=inbound_call.id,
                    request_kind=handoff_kind.value,
                    preferred_contact_method=contact_method(customer_input).value,
                    reason=(
                        "Caller requested a live transfer during the inbound call."
                        if handoff_kind is HandoffRequestKind.LIVE_TRANSFER
                        else "Caller requested a callback during the inbound call."
                    ),
                    availability=None,
                    transfer_attempted=transfer_was_attempted(
                        session,
                        inbound_call.id,
                    ),
                    status=(
                        HandoffStatus.COMPLETED.value
                        if completed_transfer is not None
                        else HandoffStatus.REQUESTED.value
                    ),
                    created_by=actor.app_user_id,
                    updated_by=actor.app_user_id,
                    completed_at=(
                        completed_transfer.occurred_at
                        if completed_transfer is not None
                        else None
                    ),
                )
            )

        conversation_session.status = ConversationSessionStatus.CONFIRMED.value
        conversation_session.confirmed_at = receipt.confirmed_at
        conversation_session.ended_at = max(
            occurred_at,
            conversation_session.authorized_at or occurred_at,
        )
        finish_call(
            inbound_call,
            occurred_at=occurred_at,
            maximum_duration_seconds=self._maximum_duration_seconds,
        )
        if inbound_call.status == InboundCallStatus.CALLBACK_PENDING.value:
            inbound_call.status = InboundCallStatus.CALLBACK_REQUESTED.value

        session.add(
            post_call_event(
                inbound_call=inbound_call,
                event_key=event_key,
                occurred_at=occurred_at,
                fingerprint=fingerprint,
                confirmation_present=True,
                resulting_status=inbound_call.status,
            )
        )
        session.add_all(
            [
                system_audit(
                    agency_id=inbound_call.agency_id,
                    event_type="CUSTOMER_CREATED",
                    summary="Customer created from confirmed phone intake",
                    details={"source": "PHONE_CONVERSATION_INTAKE"},
                    correlation_id=correlation_id,
                    customer_id=customer.id,
                ),
                system_audit(
                    agency_id=inbound_call.agency_id,
                    event_type="CONVERSATION_INTAKE_CONFIRMED",
                    summary="Phone conversation intake confirmed",
                    details={
                        "conversation_intake_id": str(intake.id),
                        "conversation_session_id": str(conversation_session.id),
                        "channel": ConversationChannel.PHONE.value,
                    },
                    correlation_id=correlation_id,
                    customer_id=customer.id,
                ),
                system_audit(
                    agency_id=inbound_call.agency_id,
                    event_type="LEAD_CREATED",
                    summary="Lead created from confirmed phone intake",
                    details={
                        "lead_id": str(lead.id),
                        "conversation_intake_id": str(intake.id),
                        "status": lead.status,
                        "urgency": lead.urgency,
                    },
                    correlation_id=correlation_id,
                    customer_id=customer.id,
                ),
            ]
        )

    def _record_unconfirmed_end(
        self,
        *,
        session: Session,
        inbound_call: InboundCall,
        event_key: str,
        fingerprint: str,
        occurred_at: datetime,
        correlation_id: UUID,
        conversation_session: ConversationSession | None = None,
    ) -> None:
        if conversation_session is not None and conversation_session.status in {
            ConversationSessionStatus.AUTHORIZED.value,
            ConversationSessionStatus.REVIEW_PENDING.value,
        }:
            conversation_session.status = ConversationSessionStatus.FAILED.value
            conversation_session.failure_code = "PHONE_INTAKE_NOT_CONFIRMED"
            conversation_session.ended_at = max(
                occurred_at,
                conversation_session.authorized_at or occurred_at,
            )
        finish_call(
            inbound_call,
            occurred_at=occurred_at,
            maximum_duration_seconds=self._maximum_duration_seconds,
        )
        if inbound_call.status == InboundCallStatus.CALLBACK_PENDING.value:
            inbound_call.status = InboundCallStatus.FAILED.value
            inbound_call.failure_code = "CALLBACK_NOT_CAPTURED"
        session.add(
            post_call_event(
                inbound_call=inbound_call,
                event_key=event_key,
                occurred_at=occurred_at,
                fingerprint=fingerprint,
                confirmation_present=False,
                resulting_status=inbound_call.status,
            )
        )
        session.add(
            system_audit(
                agency_id=inbound_call.agency_id,
                event_type="PHONE_CALL_ENDED_UNCONFIRMED",
                summary="Phone call ended without confirmed intake",
                details={"inbound_call_id": str(inbound_call.id)},
                correlation_id=correlation_id,
            )
        )

    def _record_initiation_failure(
        self,
        *,
        session: Session,
        inbound_call: InboundCall,
        conversation_session: ConversationSession | None,
        event_key: str,
        fingerprint: str,
        occurred_at: datetime,
        correlation_id: UUID,
    ) -> None:
        inbound_call.status = InboundCallStatus.FAILED.value
        inbound_call.failure_code = "PHONE_PROVIDER_INITIATION_FAILED"
        inbound_call.ended_at = max(occurred_at, inbound_call.received_at)
        if conversation_session is not None:
            conversation_session.status = ConversationSessionStatus.FAILED.value
            conversation_session.failure_code = "PROVIDER_UNAVAILABLE"
            conversation_session.ended_at = inbound_call.ended_at
        session.add(
            post_call_event(
                inbound_call=inbound_call,
                event_key=event_key,
                occurred_at=inbound_call.ended_at,
                fingerprint=fingerprint,
                confirmation_present=False,
                resulting_status=inbound_call.status,
            )
        )
        session.add(
            system_audit(
                agency_id=inbound_call.agency_id,
                event_type="PHONE_PROVIDER_INITIATION_FAILED",
                summary="Phone conversation provider initiation failed",
                details={"inbound_call_id": str(inbound_call.id)},
                correlation_id=correlation_id,
            )
        )

    def _resolve_actor(self, session: Session) -> ActorContext:
        try:
            return resolve_development_actor(
                session,
                self._development_actor_user_id,
            )
        except ActorResolutionError as error:
            raise ApiError(
                status_code=503,
                code="PHONE_DEVELOPMENT_ACTOR_UNAVAILABLE",
                message="The phone development context is unavailable",
            ) from error

    def _source_call_reference(self, inbound_call_id: UUID) -> str:
        with self._session_factory() as session:
            inbound_call = require_phone_call(session, inbound_call_id)
            return inbound_call.source_call_reference


def require_phone_call(
    session: Session,
    inbound_call_id: UUID,
    *,
    for_update: bool = False,
) -> InboundCall:
    statement = select(InboundCall).where(InboundCall.id == inbound_call_id)
    if for_update:
        statement = statement.with_for_update()
    inbound_call = session.scalar(statement)
    if inbound_call is None or inbound_call.adapter_name != "twilio":
        raise phone_context_error()
    return inbound_call


def require_phone_session_context(
    session: Session,
    request: PhoneCallContext,
    *,
    for_update: bool = False,
) -> ConversationSession:
    statement = select(ConversationSession).where(
        ConversationSession.inbound_call_id == request.inbound_call_id,
        ConversationSession.channel == ConversationChannel.PHONE.value,
    )
    if for_update:
        statement = statement.with_for_update()
    conversation_session = session.scalar(statement)
    if conversation_session is None or conversation_session.status not in {
        ConversationSessionStatus.AUTHORIZED.value,
        ConversationSessionStatus.REVIEW_PENDING.value,
    }:
        raise phone_context_error()
    require_conversation_reference(conversation_session, request.conversation_id)
    return conversation_session


def require_conversation_reference(
    conversation_session: ConversationSession,
    conversation_id: str,
) -> None:
    if (
        conversation_session.provider_metadata.get("external_session_reference")
        != conversation_id
    ):
        raise phone_context_error()


def normalize_post_call(payload: dict[str, object]) -> NormalizedPostCall:
    event_type = payload.get("type")
    event_timestamp = payload.get("event_timestamp")
    data = payload.get("data")
    if (
        not isinstance(event_type, str)
        or event_type not in {"post_call_transcription", "call_initiation_failure"}
        or not isinstance(event_timestamp, int)
        or isinstance(event_timestamp, bool)
        or not isinstance(data, dict)
    ):
        raise ApiError(
            status_code=422,
            code="PHONE_POST_CALL_EVENT_INVALID",
            message="The post-call event did not satisfy the provider contract",
        )
    conversation_id = data.get("conversation_id")
    if not isinstance(conversation_id, str):
        raise invalid_post_call_event()
    inbound_call_id: UUID | None = None
    source_call_reference: str | None = None
    if event_type == "post_call_transcription":
        initiation_data = data.get("conversation_initiation_client_data")
        if not isinstance(initiation_data, dict):
            raise invalid_post_call_event()
        dynamic_variables = initiation_data.get("dynamic_variables")
        if not isinstance(dynamic_variables, dict):
            raise invalid_post_call_event()
        raw_call_id = dynamic_variables.get("phone_inbound_call_id")
        try:
            inbound_call_id = UUID(str(raw_call_id))
        except (TypeError, ValueError) as error:
            raise invalid_post_call_event() from error
    else:
        metadata = data.get("metadata")
        metadata_body = metadata.get("body") if isinstance(metadata, dict) else None
        raw_reference = (
            metadata_body.get("CallSid") if isinstance(metadata_body, dict) else None
        )
        if not isinstance(raw_reference, str) or not raw_reference.strip():
            raise invalid_post_call_event()
        source_call_reference = raw_reference

    try:
        turns: list[ConversationTurn] = []
        raw_transcript = data.get("transcript", [])
        if not isinstance(raw_transcript, list):
            raise invalid_post_call_event()
        for raw_turn in raw_transcript:
            if not isinstance(raw_turn, dict):
                continue
            role = raw_turn.get("role")
            message = raw_turn.get("message")
            speaker: Literal["USER", "AGENT"] | None = (
                "USER" if role == "user" else "AGENT" if role == "agent" else None
            )
            if speaker is not None and isinstance(message, str) and message.strip():
                turns.append(ConversationTurn(speaker=speaker, text=message))
        return NormalizedPostCall(
            event_type=event_type,
            event_timestamp=event_timestamp,
            inbound_call_id=inbound_call_id,
            source_call_reference=source_call_reference,
            conversation_id=conversation_id,
            transcript=turns,
        )
    except ValidationError as error:
        raise invalid_post_call_event() from error


def resolve_post_call(
    session: Session,
    normalized: NormalizedPostCall,
    *,
    for_update: bool,
) -> InboundCall:
    if normalized.inbound_call_id is not None:
        return require_phone_call(
            session,
            normalized.inbound_call_id,
            for_update=for_update,
        )
    statement = select(InboundCall).where(
        InboundCall.adapter_name == "twilio",
        InboundCall.source_call_reference == normalized.source_call_reference,
    )
    if for_update:
        statement = statement.with_for_update()
    inbound_call = session.scalar(statement)
    if inbound_call is None:
        raise phone_context_error()
    return inbound_call


def requested_handoff_kind(
    session: Session,
    inbound_call_id: UUID,
) -> HandoffRequestKind | None:
    events = session.scalars(
        select(InboundCallEvent).where(
            InboundCallEvent.inbound_call_id == inbound_call_id,
            InboundCallEvent.event_type.in_(
                [
                    InboundCallEventType.TRANSFER_REQUESTED.value,
                    InboundCallEventType.TRANSFER_FAILED.value,
                    InboundCallEventType.CALLBACK_REQUESTED.value,
                ]
            ),
        )
    ).all()
    event_types = {event.event_type for event in events}
    if InboundCallEventType.TRANSFER_FAILED.value in event_types:
        return HandoffRequestKind.CALLBACK
    if InboundCallEventType.CALLBACK_REQUESTED.value in event_types:
        return HandoffRequestKind.CALLBACK
    if any(
        event.event_type == InboundCallEventType.TRANSFER_REQUESTED.value
        and event.details.get("action") == CallAction.TRANSFER.value
        for event in events
    ):
        return HandoffRequestKind.LIVE_TRANSFER
    if any(
        event.details.get("action") == CallAction.COLLECT_CALLBACK.value
        for event in events
    ):
        return HandoffRequestKind.CALLBACK
    return None


def transfer_was_attempted(session: Session, inbound_call_id: UUID) -> bool:
    events = session.scalars(
        select(InboundCallEvent).where(
            InboundCallEvent.inbound_call_id == inbound_call_id,
            InboundCallEvent.event_type
            == InboundCallEventType.TRANSFER_REQUESTED.value,
        )
    ).all()
    return any(
        event.details.get("action") == CallAction.TRANSFER.value for event in events
    )


def successful_transfer_event(
    session: Session,
    inbound_call_id: UUID,
) -> InboundCallEvent | None:
    return session.scalar(
        select(InboundCallEvent).where(
            InboundCallEvent.inbound_call_id == inbound_call_id,
            InboundCallEvent.event_type
            == InboundCallEventType.TRANSFER_SUCCEEDED.value,
        )
    )


def finish_call(
    inbound_call: InboundCall,
    *,
    occurred_at: datetime,
    maximum_duration_seconds: int,
) -> None:
    ended_at = max(occurred_at, inbound_call.received_at)
    inbound_call.ended_at = ended_at
    duration = (ended_at - inbound_call.received_at).total_seconds()
    if duration > maximum_duration_seconds:
        inbound_call.status = InboundCallStatus.FAILED.value
        inbound_call.failure_code = "DURATION_LIMIT_EXCEEDED"
    elif inbound_call.status in {
        InboundCallStatus.RECEIVED.value,
        InboundCallStatus.CONNECTED.value,
    }:
        inbound_call.status = InboundCallStatus.COMPLETED.value


def post_call_event(
    *,
    inbound_call: InboundCall,
    event_key: str,
    occurred_at: datetime,
    fingerprint: str,
    confirmation_present: bool,
    resulting_status: str,
) -> InboundCallEvent:
    return InboundCallEvent(
        agency_id=inbound_call.agency_id,
        inbound_call_id=inbound_call.id,
        event_key=event_key,
        event_type="PHONE_POST_CALL_FINALIZED",
        occurred_at=max(occurred_at, inbound_call.received_at),
        details={
            "fingerprint": fingerprint,
            "confirmation_present": confirmation_present,
            "resulting_status": resulting_status,
        },
    )


def confirmation_fingerprint(request: PhoneIntakeConfirmationInput) -> str:
    value = request.model_dump(mode="json", exclude={"explicit_verbal_confirmation"})
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def bounded_event_key(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}:{digest}"


def post_call_fingerprint(request: NormalizedPostCall) -> str:
    encoded = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def contact_method(customer: CustomerInput) -> HandoffContactMethod:
    if customer.phone is not None:
        return HandoffContactMethod.PHONE
    if customer.email is not None:
        return HandoffContactMethod.EMAIL
    return HandoffContactMethod.NO_PREFERENCE


def system_audit(
    *,
    agency_id: UUID,
    event_type: str,
    summary: str,
    details: dict[str, object],
    correlation_id: UUID,
    customer_id: UUID | None = None,
) -> AuditEvent:
    return AuditEvent(
        agency_id=agency_id,
        actor_type=AuditActorType.SYSTEM.value,
        actor_user_id=None,
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        customer_id=customer_id,
        summary=summary,
        details=details,
        correlation_id=correlation_id,
        event_version=1,
    )


def invalid_post_call_event() -> ApiError:
    return ApiError(
        status_code=422,
        code="PHONE_POST_CALL_EVENT_INVALID",
        message="The post-call event did not satisfy the provider contract",
    )


def phone_context_error() -> ApiError:
    return ApiError(
        status_code=409,
        code="PHONE_CONVERSATION_CONTEXT_INVALID",
        message="The phone conversation context is not active",
    )
