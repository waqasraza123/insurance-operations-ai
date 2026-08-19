from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.actors import ActorContext
from insurance_operations.approved_faqs.schemas import (
    ApprovedFaqCreateInput,
    ApprovedFaqLookupResponse,
    ApprovedFaqResponse,
    ApprovedFaqSource,
    ApprovedFaqStatusInput,
    ApprovedFaqUpdateInput,
)
from insurance_operations.database.models.approved_faq import (
    AgencyApprovedFaq,
    ApprovedFaqStatus,
)
from insurance_operations.database.models.conversation import (
    ConversationChannel,
    ConversationSession,
    ConversationSessionStatus,
)
from insurance_operations.database.models.operations import AuditActorType, AuditEvent
from insurance_operations.database.models.receptionist import (
    AgencyReceptionistSettings,
)
from insurance_operations.errors import ApiError

_IGNORED_MATCH_WORDS = frozenset(
    {
        "a",
        "an",
        "are",
        "can",
        "could",
        "do",
        "does",
        "for",
        "i",
        "is",
        "me",
        "my",
        "of",
        "please",
        "tell",
        "the",
        "to",
        "what",
        "when",
        "which",
        "you",
        "your",
    }
)
_MINIMUM_MATCH_SCORE = 0.8
_MINIMUM_LEAD_OVER_SECOND = 0.08


class ApprovedFaqService:
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list(self, *, actor: ActorContext) -> list[ApprovedFaqResponse]:
        with self._session_factory() as session:
            faqs = session.scalars(
                select(AgencyApprovedFaq)
                .where(AgencyApprovedFaq.agency_id == actor.agency_id)
                .order_by(
                    AgencyApprovedFaq.status,
                    AgencyApprovedFaq.created_at,
                    AgencyApprovedFaq.id,
                )
            ).all()
            return [faq_response(faq) for faq in faqs]

    def create(
        self,
        *,
        actor: ActorContext,
        request: ApprovedFaqCreateInput,
        correlation_id: UUID,
    ) -> ApprovedFaqResponse:
        faq = AgencyApprovedFaq(
            agency_id=actor.agency_id,
            question=request.question,
            normalized_question=normalize_faq_question(request.question),
            approved_answer=request.approved_answer,
            status=request.status,
            created_by=actor.app_user_id,
            updated_by=actor.app_user_id,
        )
        try:
            with self._session_factory() as session, session.begin():
                session.add(faq)
                session.flush()
                session.refresh(faq)
                session.add(
                    faq_audit_event(
                        actor=actor,
                        event_type="AGENCY_APPROVED_FAQ_CREATED",
                        summary="Agency-approved FAQ created",
                        faq=faq,
                        correlation_id=correlation_id,
                    )
                )
                return faq_response(faq)
        except IntegrityError as error:
            raise duplicate_faq_error() from error

    def update(
        self,
        *,
        actor: ActorContext,
        faq_id: UUID,
        request: ApprovedFaqUpdateInput,
        correlation_id: UUID,
    ) -> ApprovedFaqResponse:
        try:
            with self._session_factory() as session, session.begin():
                faq = self._get_owned_for_update(session, actor, faq_id)
                require_faq_version(faq, request.expected_row_version)
                faq.question = request.question
                faq.normalized_question = normalize_faq_question(request.question)
                faq.approved_answer = request.approved_answer
                faq.updated_by = actor.app_user_id
                session.flush()
                session.refresh(faq)
                session.add(
                    faq_audit_event(
                        actor=actor,
                        event_type="AGENCY_APPROVED_FAQ_UPDATED",
                        summary="Agency-approved FAQ updated",
                        faq=faq,
                        correlation_id=correlation_id,
                    )
                )
                return faq_response(faq)
        except IntegrityError as error:
            raise duplicate_faq_error() from error

    def set_status(
        self,
        *,
        actor: ActorContext,
        faq_id: UUID,
        request: ApprovedFaqStatusInput,
        status: ApprovedFaqStatus,
        correlation_id: UUID,
    ) -> ApprovedFaqResponse:
        with self._session_factory() as session, session.begin():
            faq = self._get_owned_for_update(session, actor, faq_id)
            require_faq_version(faq, request.expected_row_version)
            faq.status = status.value
            faq.updated_by = actor.app_user_id
            session.flush()
            session.refresh(faq)
            session.add(
                faq_audit_event(
                    actor=actor,
                    event_type=f"AGENCY_APPROVED_FAQ_{status.value}",
                    summary=f"Agency-approved FAQ {status.value.lower()}",
                    faq=faq,
                    correlation_id=correlation_id,
                )
            )
            return faq_response(faq)

    def preview_lookup(
        self,
        *,
        actor: ActorContext,
        query: str,
    ) -> ApprovedFaqLookupResponse:
        with self._session_factory() as session:
            return self._lookup(session, actor.agency_id, query)

    def conversation_lookup(
        self,
        *,
        actor: ActorContext,
        conversation_session_id: UUID,
        query: str,
        correlation_id: UUID,
    ) -> ApprovedFaqLookupResponse:
        now = datetime.now(UTC)
        with self._session_factory() as session, session.begin():
            conversation_session = session.get(
                ConversationSession,
                conversation_session_id,
            )
            if (
                conversation_session is None
                or conversation_session.agency_id != actor.agency_id
                or conversation_session.initiated_by != actor.app_user_id
                or conversation_session.status
                != ConversationSessionStatus.AUTHORIZED.value
                or conversation_session.authorization_expires_at <= now
            ):
                raise ApiError(
                    status_code=409,
                    code="CONVERSATION_SESSION_NOT_ACTIVE",
                    message="The conversation session is not active",
                )
            result = self._lookup(session, actor.agency_id, query)
            if result.source is not None:
                session.add(
                    AuditEvent(
                        agency_id=actor.agency_id,
                        actor_type=AuditActorType.DEMO_USER.value,
                        actor_user_id=actor.app_user_id,
                        event_type="AGENCY_APPROVED_FAQ_ANSWER_USED",
                        occurred_at=now,
                        summary="Agency-approved FAQ answer supplied",
                        details={
                            "conversation_session_id": str(conversation_session.id),
                            "faq_id": str(result.source.faq_id),
                            "faq_row_version": result.source.row_version,
                        },
                        correlation_id=correlation_id,
                        event_version=1,
                    )
                )
            return result

    def phone_conversation_lookup(
        self,
        *,
        inbound_call_id: UUID,
        conversation_id: str,
        query: str,
        correlation_id: UUID,
    ) -> ApprovedFaqLookupResponse:
        now = datetime.now(UTC)
        with self._session_factory() as session, session.begin():
            conversation_session = session.scalar(
                select(ConversationSession).where(
                    ConversationSession.inbound_call_id == inbound_call_id,
                    ConversationSession.channel == ConversationChannel.PHONE.value,
                )
            )
            if (
                conversation_session is None
                or conversation_session.status
                != ConversationSessionStatus.AUTHORIZED.value
                or conversation_session.authorization_expires_at <= now
                or conversation_session.provider_metadata.get(
                    "external_session_reference"
                )
                != conversation_id
            ):
                raise ApiError(
                    status_code=409,
                    code="CONVERSATION_SESSION_NOT_ACTIVE",
                    message="The conversation session is not active",
                )
            result = self._lookup(
                session,
                conversation_session.agency_id,
                query,
            )
            if result.source is not None:
                session.add(
                    AuditEvent(
                        agency_id=conversation_session.agency_id,
                        actor_type=AuditActorType.SYSTEM.value,
                        actor_user_id=None,
                        event_type="AGENCY_APPROVED_FAQ_ANSWER_USED",
                        occurred_at=now,
                        summary="Agency-approved FAQ answer supplied",
                        details={
                            "conversation_session_id": str(conversation_session.id),
                            "faq_id": str(result.source.faq_id),
                            "faq_row_version": result.source.row_version,
                            "channel": ConversationChannel.PHONE.value,
                        },
                        correlation_id=correlation_id,
                        event_version=1,
                    )
                )
            return result

    def _lookup(
        self,
        session: Session,
        agency_id: UUID,
        query: str,
    ) -> ApprovedFaqLookupResponse:
        settings = session.scalar(
            select(AgencyReceptionistSettings).where(
                AgencyReceptionistSettings.agency_id == agency_id
            )
        )
        if settings is None:
            raise ApiError(
                status_code=409,
                code="RECEPTIONIST_SETTINGS_REQUIRED",
                message="Receptionist settings must be configured first",
            )
        faqs = session.scalars(
            select(AgencyApprovedFaq).where(
                AgencyApprovedFaq.agency_id == agency_id,
                AgencyApprovedFaq.status == ApprovedFaqStatus.ACTIVE.value,
            )
        ).all()
        match = select_faq_match(query, faqs)
        if match is None:
            return ApprovedFaqLookupResponse(
                matched=False,
                answer=None,
                fallback_message=settings.escalation_message,
                source=None,
            )
        return ApprovedFaqLookupResponse(
            matched=True,
            answer=match.approved_answer,
            fallback_message=settings.escalation_message,
            source=ApprovedFaqSource(
                faq_id=match.id,
                question=match.question,
                row_version=match.row_version,
            ),
        )

    @staticmethod
    def _get_owned_for_update(
        session: Session,
        actor: ActorContext,
        faq_id: UUID,
    ) -> AgencyApprovedFaq:
        faq = session.scalar(
            select(AgencyApprovedFaq)
            .where(
                AgencyApprovedFaq.id == faq_id,
                AgencyApprovedFaq.agency_id == actor.agency_id,
            )
            .with_for_update()
        )
        if faq is None:
            raise ApiError(
                status_code=404,
                code="APPROVED_FAQ_NOT_FOUND",
                message="The approved FAQ was not found",
            )
        return faq


def normalize_faq_question(value: str) -> str:
    characters = [
        character.casefold() if character.isalnum() else " " for character in value
    ]
    return " ".join("".join(characters).split())


def select_faq_match(
    query: str,
    faqs: Sequence[AgencyApprovedFaq],
) -> AgencyApprovedFaq | None:
    scored = sorted(
        ((faq_match_score(query, faq.question), str(faq.id), faq) for faq in faqs),
        key=lambda item: (-item[0], item[1]),
    )
    if not scored or scored[0][0] < _MINIMUM_MATCH_SCORE:
        return None
    if (
        len(scored) > 1
        and scored[1][0] >= _MINIMUM_MATCH_SCORE
        and scored[0][0] - scored[1][0] < _MINIMUM_LEAD_OVER_SECOND
    ):
        return None
    return scored[0][2]


def faq_match_score(query: str, question: str) -> float:
    normalized_query = normalize_faq_question(query)
    normalized_question = normalize_faq_question(question)
    if normalized_query == normalized_question:
        return 1.0
    query_tokens = meaningful_tokens(normalized_query)
    question_tokens = meaningful_tokens(normalized_question)
    if not query_tokens or not question_tokens:
        return 0.0
    if query_tokens == question_tokens:
        return 1.0
    overlap = query_tokens & question_tokens
    required_overlap = 1 if len(question_tokens) == 1 else 2
    if len(overlap) < required_overlap:
        return 0.0
    coverage = len(overlap) / len(question_tokens)
    precision = len(overlap) / len(query_tokens)
    if coverage < 0.75:
        return 0.0
    return (coverage * 2 + precision) / 3


def meaningful_tokens(normalized_value: str) -> set[str]:
    return {
        token for token in normalized_value.split() if token not in _IGNORED_MATCH_WORDS
    }


def faq_response(faq: AgencyApprovedFaq) -> ApprovedFaqResponse:
    return ApprovedFaqResponse(
        id=faq.id,
        agency_id=faq.agency_id,
        question=faq.question,
        approved_answer=faq.approved_answer,
        status=faq.status,
        row_version=faq.row_version,
        created_at=faq.created_at,
        updated_at=faq.updated_at,
    )


def require_faq_version(faq: AgencyApprovedFaq, expected_row_version: int) -> None:
    if faq.row_version != expected_row_version:
        raise ApiError(
            status_code=409,
            code="APPROVED_FAQ_VERSION_CONFLICT",
            message="The approved FAQ was changed by another request",
            details={"current_row_version": faq.row_version},
        )


def duplicate_faq_error() -> ApiError:
    return ApiError(
        status_code=409,
        code="APPROVED_FAQ_ALREADY_EXISTS",
        message="An approved FAQ with this question already exists",
    )


def faq_audit_event(
    *,
    actor: ActorContext,
    event_type: str,
    summary: str,
    faq: AgencyApprovedFaq,
    correlation_id: UUID,
) -> AuditEvent:
    return AuditEvent(
        agency_id=actor.agency_id,
        actor_type=AuditActorType.STAFF.value,
        actor_user_id=actor.app_user_id,
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        summary=summary,
        details={
            "faq_id": str(faq.id),
            "faq_status": faq.status,
            "faq_row_version": faq.row_version,
        },
        correlation_id=correlation_id,
        event_version=1,
    )
