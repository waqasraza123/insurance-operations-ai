import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.actors import ActorContext
from insurance_operations.conversations.contracts import (
    ConversationProvider,
    ConversationProviderError,
)
from insurance_operations.conversations.schemas import (
    ConversationConnection,
    ConversationEndOutcome,
    ConversationEndResponse,
    ConversationIntakeConfirmationInput,
    ConversationIntakeResponse,
    ConversationSessionCreateInput,
    ConversationSessionResponse,
)
from insurance_operations.customers import customer_from_input, customer_view
from insurance_operations.database.models.conversation import (
    ConversationIntake,
    ConversationSession,
    ConversationSessionStatus,
)
from insurance_operations.database.models.identity import Agency
from insurance_operations.database.models.operations import (
    AuditActorType,
    AuditEvent,
    IdempotencyRecord,
    IdempotencyStatus,
)
from insurance_operations.errors import ApiError
from insurance_operations.settings import ApiSettings

CONFIRM_INTAKE_ROUTE_KEY = "POST /api/v1/development/conversation-intakes"
ACTIVE_SESSION_STATUSES = {
    ConversationSessionStatus.REQUESTING.value,
    ConversationSessionStatus.AUTHORIZED.value,
}


class ConversationService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        settings: ApiSettings,
        provider: ConversationProvider,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._provider = provider

    def authorize_session(
        self,
        *,
        actor: ActorContext,
        request: ConversationSessionCreateInput,
    ) -> ConversationSessionResponse:
        if not request.ai_disclosure_accepted:
            raise ApiError(
                status_code=422,
                code="AI_DISCLOSURE_REQUIRED",
                message="AI disclosure acceptance is required",
            )
        if not request.microphone_consent_granted:
            raise ApiError(
                status_code=422,
                code="MICROPHONE_CONSENT_REQUIRED",
                message="Microphone consent is required",
            )
        if not request.synthetic_data_acknowledged:
            raise ApiError(
                status_code=422,
                code="SYNTHETIC_DATA_ACKNOWLEDGEMENT_REQUIRED",
                message="Synthetic-data acknowledgement is required",
            )

        now = datetime.now(UTC)
        authorization_expires_at = now + timedelta(
            seconds=self._settings.conversation_max_duration_seconds
        )
        confirmation_expires_at = now + timedelta(
            minutes=self._settings.conversation_confirmation_window_minutes
        )
        with self._session_factory() as session, session.begin():
            self._lock_agency(session, actor.agency_id)
            self._expire_stale_sessions(session, actor.agency_id, now)
            self._enforce_daily_limit(session, actor.agency_id, now)
            self._enforce_concurrency_limit(session, actor.agency_id, now)
            conversation_session = ConversationSession(
                agency_id=actor.agency_id,
                initiated_by=actor.app_user_id,
                status=ConversationSessionStatus.REQUESTING.value,
                disclosure_accepted_at=now,
                microphone_consent_at=now,
                synthetic_data_acknowledged_at=now,
                maximum_duration_seconds=(
                    self._settings.conversation_max_duration_seconds
                ),
                authorization_expires_at=authorization_expires_at,
                confirmation_expires_at=confirmation_expires_at,
            )
            session.add(conversation_session)
            session.flush()
            conversation_session_id = conversation_session.id

        try:
            grant = self._provider.authorize_session()
        except ConversationProviderError as error:
            with self._session_factory() as session, session.begin():
                failed_session = session.get(
                    ConversationSession,
                    conversation_session_id,
                    with_for_update=True,
                )
                if failed_session is not None:
                    failed_session.status = ConversationSessionStatus.FAILED.value
                    failed_session.failure_code = "PROVIDER_UNAVAILABLE"
                    failed_session.ended_at = datetime.now(UTC)
            raise ApiError(
                status_code=503,
                code="CONVERSATION_PROVIDER_UNAVAILABLE",
                message="The voice service is temporarily unavailable",
            ) from error

        authorized_at = datetime.now(UTC)
        with self._session_factory() as session, session.begin():
            authorized_session = session.get(
                ConversationSession,
                conversation_session_id,
                with_for_update=True,
            )
            if authorized_session is None:
                raise RuntimeError("conversation session was not persisted")
            authorized_session.status = ConversationSessionStatus.AUTHORIZED.value
            authorized_session.authorized_at = authorized_at
            authorized_session.provider_metadata = grant.metadata.as_storage_value()

        return ConversationSessionResponse(
            session_id=conversation_session_id,
            connection=ConversationConnection(
                transport=grant.transport,
                credential=grant.credential,
            ),
            maximum_duration_seconds=self._settings.conversation_max_duration_seconds,
            confirmation_expires_at=confirmation_expires_at,
        )

    def end_session(
        self,
        *,
        actor: ActorContext,
        conversation_session_id: UUID,
        outcome: ConversationEndOutcome,
    ) -> ConversationEndResponse:
        now = datetime.now(UTC)
        with self._session_factory() as session, session.begin():
            conversation_session = session.get(
                ConversationSession,
                conversation_session_id,
                with_for_update=True,
            )
            conversation_session = self._require_owned_session(
                conversation_session,
                actor,
            )

            if conversation_session.confirmation_expires_at <= now:
                raise ApiError(
                    status_code=410,
                    code="CONVERSATION_SESSION_EXPIRED",
                    message="The conversation session has expired",
                )

            authorized_at = conversation_session.authorized_at
            duration_exceeded = (
                authorized_at is not None
                and now
                > authorized_at
                + timedelta(seconds=conversation_session.maximum_duration_seconds)
            )

            if outcome is ConversationEndOutcome.COMPLETED:
                if duration_exceeded and conversation_session.status == (
                    ConversationSessionStatus.AUTHORIZED.value
                ):
                    conversation_session.status = (
                        ConversationSessionStatus.EXPIRED.value
                    )
                    conversation_session.failure_code = "DURATION_LIMIT_EXCEEDED"
                    conversation_session.ended_at = now
                elif conversation_session.status == (
                    ConversationSessionStatus.AUTHORIZED.value
                ):
                    conversation_session.status = (
                        ConversationSessionStatus.REVIEW_PENDING.value
                    )
                    conversation_session.ended_at = now
                elif conversation_session.status not in {
                    ConversationSessionStatus.REVIEW_PENDING.value,
                    ConversationSessionStatus.CONFIRMED.value,
                }:
                    raise self._session_state_conflict()
            else:
                expected_code = (
                    "CLIENT_INTERRUPTED"
                    if outcome is ConversationEndOutcome.INTERRUPTED
                    else "CLIENT_FAILED"
                )
                if conversation_session.status in ACTIVE_SESSION_STATUSES:
                    conversation_session.status = ConversationSessionStatus.FAILED.value
                    conversation_session.failure_code = expected_code
                    conversation_session.ended_at = now
                elif not (
                    conversation_session.status
                    == ConversationSessionStatus.FAILED.value
                    and conversation_session.failure_code == expected_code
                ):
                    raise self._session_state_conflict()

            return ConversationEndResponse(
                session_id=conversation_session.id,
                status=conversation_session.status,
                review_available=(
                    conversation_session.status
                    in {
                        ConversationSessionStatus.REVIEW_PENDING.value,
                        ConversationSessionStatus.CONFIRMED.value,
                    }
                ),
                confirmation_expires_at=conversation_session.confirmation_expires_at,
            )

    def confirm_intake(
        self,
        *,
        actor: ActorContext,
        request: ConversationIntakeConfirmationInput,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[ConversationIntakeResponse, bool]:
        now = datetime.now(UTC)
        fingerprint = request_fingerprint(request)
        idempotency_insert = (
            insert(IdempotencyRecord)
            .values(
                agency_id=actor.agency_id,
                actor_scope_type="APP_USER",
                actor_scope_id=actor.app_user_id,
                route_key=CONFIRM_INTAKE_ROUTE_KEY,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                status=IdempotencyStatus.IN_PROGRESS.value,
                expires_at=now
                + timedelta(hours=self._settings.idempotency_retention_hours),
            )
            .on_conflict_do_nothing(
                constraint="uq_idempotency_records_scope",
            )
            .returning(IdempotencyRecord.id)
        )

        with self._session_factory() as session, session.begin():
            record_id = session.scalar(idempotency_insert)
            if record_id is None:
                existing_record = session.scalar(
                    select(IdempotencyRecord)
                    .where(
                        IdempotencyRecord.actor_scope_type == "APP_USER",
                        IdempotencyRecord.actor_scope_id == actor.app_user_id,
                        IdempotencyRecord.route_key == CONFIRM_INTAKE_ROUTE_KEY,
                        IdempotencyRecord.idempotency_key == idempotency_key,
                    )
                    .with_for_update()
                )
                return replay_intake_confirmation(existing_record, fingerprint), True

            conversation_session = session.get(
                ConversationSession,
                request.conversation_session_id,
                with_for_update=True,
            )
            conversation_session = self._require_owned_session(
                conversation_session,
                actor,
            )
            if conversation_session.confirmation_expires_at <= now:
                raise ApiError(
                    status_code=410,
                    code="CONVERSATION_SESSION_EXPIRED",
                    message="The conversation confirmation window has expired",
                )
            if conversation_session.status != (
                ConversationSessionStatus.REVIEW_PENDING.value
            ):
                raise self._session_state_conflict()

            customer = customer_from_input(request.customer, actor)
            session.add(customer)
            session.flush()
            conversation_intake = ConversationIntake(
                agency_id=actor.agency_id,
                customer_id=customer.id,
                conversation_session_id=conversation_session.id,
                created_by=actor.app_user_id,
                intake_intent=request.intake_intent,
                confirmed_transcript=[
                    turn.model_dump(mode="json") for turn in request.transcript
                ],
                confirmed_at=now,
            )
            session.add(conversation_intake)
            session.flush()

            response = ConversationIntakeResponse(
                conversation_intake_id=conversation_intake.id,
                conversation_session_id=conversation_session.id,
                customer=customer_view(customer),
                confirmed_at=now,
            )
            session.add_all(
                [
                    AuditEvent(
                        agency_id=actor.agency_id,
                        actor_type=AuditActorType.STAFF.value,
                        actor_user_id=actor.app_user_id,
                        event_type="CUSTOMER_CREATED",
                        occurred_at=now,
                        customer_id=customer.id,
                        summary="Customer created from confirmed conversation intake",
                        details={"source": "CONVERSATION_INTAKE"},
                        correlation_id=correlation_id,
                        event_version=1,
                    ),
                    AuditEvent(
                        agency_id=actor.agency_id,
                        actor_type=AuditActorType.STAFF.value,
                        actor_user_id=actor.app_user_id,
                        event_type="CONVERSATION_INTAKE_CONFIRMED",
                        occurred_at=now,
                        customer_id=customer.id,
                        summary="Conversation intake confirmed",
                        details={
                            "conversation_intake_id": str(conversation_intake.id),
                            "conversation_session_id": str(conversation_session.id),
                        },
                        correlation_id=correlation_id,
                        event_version=1,
                    ),
                ]
            )
            conversation_session.status = ConversationSessionStatus.CONFIRMED.value
            conversation_session.confirmed_at = now

            idempotency_record = session.get(IdempotencyRecord, record_id)
            if idempotency_record is None:
                raise RuntimeError("idempotency record was not persisted")
            idempotency_record.status = IdempotencyStatus.COMPLETED.value
            idempotency_record.response_status = 201
            idempotency_record.response_body = response.model_dump(mode="json")
            idempotency_record.resource_type = "CONVERSATION_INTAKE"
            idempotency_record.resource_id = conversation_intake.id
            idempotency_record.completed_at = now

        return response, False

    @staticmethod
    def _lock_agency(session: Session, agency_id: UUID) -> None:
        agency = session.scalar(
            select(Agency.id).where(Agency.id == agency_id).with_for_update()
        )
        if agency is None:
            raise ApiError(
                status_code=404,
                code="DEVELOPMENT_CONTEXT_NOT_FOUND",
                message="The development context is unavailable",
            )

    @staticmethod
    def _expire_stale_sessions(
        session: Session,
        agency_id: UUID,
        now: datetime,
    ) -> None:
        session.execute(
            update(ConversationSession)
            .where(
                ConversationSession.agency_id == agency_id,
                ConversationSession.status.in_(ACTIVE_SESSION_STATUSES),
                ConversationSession.authorization_expires_at <= now,
            )
            .values(
                status=ConversationSessionStatus.EXPIRED.value,
                failure_code="AUTHORIZATION_EXPIRED",
            )
        )

    def _enforce_daily_limit(
        self,
        session: Session,
        agency_id: UUID,
        now: datetime,
    ) -> None:
        day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
        authorized_count = session.scalar(
            select(func.count())
            .select_from(ConversationSession)
            .where(
                ConversationSession.agency_id == agency_id,
                ConversationSession.authorized_at >= day_start,
            )
        )
        if authorized_count is not None and authorized_count >= (
            self._settings.conversation_daily_session_limit
        ):
            next_day = day_start + timedelta(days=1)
            retry_after = max(1, int((next_day - now).total_seconds()))
            raise ApiError(
                status_code=429,
                code="CONVERSATION_DAILY_LIMIT_REACHED",
                message="The daily conversation limit has been reached",
                headers={"Retry-After": str(retry_after)},
            )

    @staticmethod
    def _enforce_concurrency_limit(
        session: Session,
        agency_id: UUID,
        now: datetime,
    ) -> None:
        active_session_id = session.scalar(
            select(ConversationSession.id).where(
                ConversationSession.agency_id == agency_id,
                ConversationSession.status.in_(ACTIVE_SESSION_STATUSES),
                ConversationSession.authorization_expires_at > now,
            )
        )
        if active_session_id is not None:
            raise ApiError(
                status_code=409,
                code="CONVERSATION_ALREADY_ACTIVE",
                message="Another conversation is already active",
            )

    @staticmethod
    def _require_owned_session(
        conversation_session: ConversationSession | None,
        actor: ActorContext,
    ) -> ConversationSession:
        if (
            conversation_session is None
            or conversation_session.agency_id != actor.agency_id
            or conversation_session.initiated_by != actor.app_user_id
        ):
            raise ApiError(
                status_code=404,
                code="CONVERSATION_SESSION_NOT_FOUND",
                message="The conversation session was not found",
            )
        return conversation_session

    @staticmethod
    def _session_state_conflict() -> ApiError:
        return ApiError(
            status_code=409,
            code="CONVERSATION_STATE_CONFLICT",
            message="The conversation is not in the required state",
        )


def replay_intake_confirmation(
    record: IdempotencyRecord | None,
    fingerprint: str,
) -> ConversationIntakeResponse:
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
            message="The original confirmation is still in progress",
        )
    return ConversationIntakeResponse.model_validate(record.response_body)


def request_fingerprint(request: ConversationIntakeConfirmationInput) -> str:
    canonical_request = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_request.encode()).hexdigest()
