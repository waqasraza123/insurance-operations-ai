from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware

from insurance_operations.actors import (
    ActorContext,
    ActorResolutionError,
    resolve_development_actor,
)
from insurance_operations.approved_faqs import (
    ApprovedFaqCreateInput,
    ApprovedFaqLookupInput,
    ApprovedFaqLookupResponse,
    ApprovedFaqResponse,
    ApprovedFaqService,
    ApprovedFaqStatusInput,
    ApprovedFaqUpdateInput,
)
from insurance_operations.conversations.contracts import ConversationProvider
from insurance_operations.conversations.providers import (
    ElevenLabsConversationProvider,
)
from insurance_operations.conversations.schemas import (
    ConversationEndInput,
    ConversationEndResponse,
    ConversationIntakeConfirmationInput,
    ConversationIntakeResponse,
    ConversationSessionCreateInput,
    ConversationSessionResponse,
)
from insurance_operations.conversations.service import ConversationService
from insurance_operations.database.connection import (
    DatabaseReadinessError,
    check_database_readiness,
)
from insurance_operations.database.models.approved_faq import ApprovedFaqStatus
from insurance_operations.database.models.lead import LeadStatus
from insurance_operations.database.models.telephony import InboundCallStatus
from insurance_operations.errors import ApiError, api_error_handler
from insurance_operations.leads import (
    HandoffRequestCreateInput,
    HandoffRequestResponse,
    HandoffStatusInput,
    LeadDetailResponse,
    LeadListResponse,
    LeadService,
    LeadStatusInput,
    LeadUpdateInput,
)
from insurance_operations.receptionist import (
    ReceptionistSettingsInput,
    ReceptionistSettingsResponse,
    ReceptionistSettingsService,
)
from insurance_operations.settings import ApiSettings, RuntimeEnvironment
from insurance_operations.telephony import (
    CallPolicyInput,
    CallPolicyResponse,
    InboundCallActionResponse,
    InboundCallEventInput,
    InboundCallLinkLeadInput,
    InboundCallListResponse,
    InboundCallReceiveInput,
    InboundCallResponse,
    InboundNumberCreateInput,
    InboundNumberResponse,
    InboundNumberStatusInput,
    TelephonyService,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["api"]
    environment: str


class ReadinessResponse(HealthResponse):
    database: Literal["ready"]


def create_app(
    settings: ApiSettings,
    database_engine: Engine,
    conversation_provider: ConversationProvider | None = None,
) -> FastAPI:
    session_factory = sessionmaker(
        bind=database_engine,
        class_=Session,
        expire_on_commit=False,
    )
    provider = conversation_provider or default_conversation_provider(settings)
    conversation_service = (
        ConversationService(
            session_factory=session_factory,
            settings=settings,
            provider=provider,
        )
        if provider is not None
        else None
    )
    receptionist_settings_service = ReceptionistSettingsService(
        session_factory=session_factory
    )
    approved_faq_service = ApprovedFaqService(session_factory=session_factory)
    lead_service = LeadService(
        session_factory=session_factory,
        idempotency_retention_hours=settings.idempotency_retention_hours,
    )
    telephony_service = TelephonyService(session_factory=session_factory)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        yield
        if provider is not None:
            provider.close()
        database_engine.dispose()

    application = FastAPI(
        title="Insurance Operations AI API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-Correlation-ID"],
        expose_headers=["Idempotent-Replayed", "X-Correlation-ID"],
    )

    @application.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, ApiError):
            raise error
        return await api_error_handler(request, error)

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        field_errors = [
            {
                "path": ".".join(str(part) for part in item["loc"]),
                "message": item["msg"],
                "type": item["type"],
            }
            for item in error.errors()
        ]
        validation_error = ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_FAILED",
            message="The request did not satisfy the API contract",
            details={"fields": field_errors},
        )
        return await api_error_handler(request, validation_error)

    @application.middleware("http")
    async def add_correlation_id(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        raw_correlation_id = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = UUID(raw_correlation_id) if raw_correlation_id else uuid4()
        except ValueError:
            correlation_id = uuid4()
        request.state.correlation_id = str(correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = str(correlation_id)
        return response

    def require_conversation_service() -> ConversationService:
        if (
            not settings.conversation_ai_enabled
            or settings.app_environment is not RuntimeEnvironment.DEVELOPMENT
            or conversation_service is None
        ):
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOT_FOUND",
                message="The requested resource was not found",
            )
        return conversation_service

    def development_actor() -> ActorContext:
        if (
            settings.app_environment is not RuntimeEnvironment.DEVELOPMENT
            or settings.development_actor_user_id is None
        ):
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="DEVELOPMENT_CONTEXT_NOT_FOUND",
                message="The development context is unavailable",
            )
        try:
            with session_factory() as session:
                return resolve_development_actor(
                    session,
                    settings.development_actor_user_id,
                )
        except ActorResolutionError as error:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="DEVELOPMENT_CONTEXT_NOT_FOUND",
                message="The development context is unavailable",
            ) from error

    def conversation_actor(
        service: Annotated[
            ConversationService,
            Depends(require_conversation_service),
        ],
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ActorContext:
        del service
        return actor

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="api",
            environment=settings.app_environment,
        )

    @application.get("/ready", response_model=ReadinessResponse)
    def ready() -> ReadinessResponse:
        try:
            check_database_readiness(database_engine)
        except DatabaseReadinessError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            ) from error

        return ReadinessResponse(
            status="ok",
            service="api",
            environment=settings.app_environment,
            database="ready",
        )

    @application.post(
        "/api/v1/development/conversation-sessions",
        response_model=ConversationSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def post_conversation_session(
        conversation_input: ConversationSessionCreateInput,
        actor: Annotated[ActorContext, Depends(conversation_actor)],
        service: Annotated[
            ConversationService,
            Depends(require_conversation_service),
        ],
    ) -> ConversationSessionResponse:
        return service.authorize_session(actor=actor, request=conversation_input)

    @application.get(
        "/api/v1/development/receptionist-settings",
        response_model=ReceptionistSettingsResponse,
    )
    def get_receptionist_settings(
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ReceptionistSettingsResponse:
        return receptionist_settings_service.get(actor=actor)

    @application.put(
        "/api/v1/development/receptionist-settings",
        response_model=ReceptionistSettingsResponse,
    )
    def put_receptionist_settings(
        request: Request,
        settings_input: ReceptionistSettingsInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ReceptionistSettingsResponse:
        return receptionist_settings_service.replace(
            actor=actor,
            request=settings_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.get(
        "/api/v1/development/approved-faqs",
        response_model=list[ApprovedFaqResponse],
    )
    def get_approved_faqs(
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> list[ApprovedFaqResponse]:
        return approved_faq_service.list(actor=actor)

    @application.post(
        "/api/v1/development/approved-faqs",
        response_model=ApprovedFaqResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def post_approved_faq(
        request: Request,
        faq_input: ApprovedFaqCreateInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ApprovedFaqResponse:
        return approved_faq_service.create(
            actor=actor,
            request=faq_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/approved-faqs/lookup",
        response_model=ApprovedFaqLookupResponse,
    )
    def post_approved_faq_lookup_preview(
        lookup_input: ApprovedFaqLookupInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ApprovedFaqLookupResponse:
        return approved_faq_service.preview_lookup(
            actor=actor,
            query=lookup_input.query,
        )

    @application.put(
        "/api/v1/development/approved-faqs/{faq_id}",
        response_model=ApprovedFaqResponse,
    )
    def put_approved_faq(
        request: Request,
        faq_id: UUID,
        faq_input: ApprovedFaqUpdateInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ApprovedFaqResponse:
        return approved_faq_service.update(
            actor=actor,
            faq_id=faq_id,
            request=faq_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/approved-faqs/{faq_id}/activate",
        response_model=ApprovedFaqResponse,
    )
    def post_approved_faq_activate(
        request: Request,
        faq_id: UUID,
        status_input: ApprovedFaqStatusInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ApprovedFaqResponse:
        return approved_faq_service.set_status(
            actor=actor,
            faq_id=faq_id,
            request=status_input,
            status=ApprovedFaqStatus.ACTIVE,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/approved-faqs/{faq_id}/deactivate",
        response_model=ApprovedFaqResponse,
    )
    def post_approved_faq_deactivate(
        request: Request,
        faq_id: UUID,
        status_input: ApprovedFaqStatusInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> ApprovedFaqResponse:
        return approved_faq_service.set_status(
            actor=actor,
            faq_id=faq_id,
            request=status_input,
            status=ApprovedFaqStatus.INACTIVE,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/conversation-sessions/"
        "{conversation_session_id}/approved-faq-lookup",
        response_model=ApprovedFaqLookupResponse,
    )
    def post_conversation_approved_faq_lookup(
        request: Request,
        conversation_session_id: UUID,
        lookup_input: ApprovedFaqLookupInput,
        actor: Annotated[ActorContext, Depends(conversation_actor)],
    ) -> ApprovedFaqLookupResponse:
        return approved_faq_service.conversation_lookup(
            actor=actor,
            conversation_session_id=conversation_session_id,
            query=lookup_input.query,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.get(
        "/api/v1/development/leads",
        response_model=LeadListResponse,
    )
    def get_leads(
        actor: Annotated[ActorContext, Depends(development_actor)],
        lead_status: Annotated[LeadStatus | None, Query(alias="status")] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> LeadListResponse:
        return lead_service.list(
            actor=actor,
            status=lead_status,
            limit=limit,
            offset=offset,
        )

    @application.get(
        "/api/v1/development/leads/{lead_id}",
        response_model=LeadDetailResponse,
    )
    def get_lead(
        lead_id: UUID,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> LeadDetailResponse:
        return lead_service.get(actor=actor, lead_id=lead_id)

    @application.put(
        "/api/v1/development/leads/{lead_id}",
        response_model=LeadDetailResponse,
    )
    def put_lead(
        request: Request,
        lead_id: UUID,
        lead_input: LeadUpdateInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> LeadDetailResponse:
        return lead_service.update(
            actor=actor,
            lead_id=lead_id,
            request=lead_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/leads/{lead_id}/status",
        response_model=LeadDetailResponse,
    )
    def post_lead_status(
        request: Request,
        lead_id: UUID,
        status_input: LeadStatusInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> LeadDetailResponse:
        return lead_service.set_status(
            actor=actor,
            lead_id=lead_id,
            request=status_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.get(
        "/api/v1/development/leads/{lead_id}/handoff-requests",
        response_model=list[HandoffRequestResponse],
    )
    def get_lead_handoff_requests(
        lead_id: UUID,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> list[HandoffRequestResponse]:
        return lead_service.list_handoffs(actor=actor, lead_id=lead_id)

    @application.post(
        "/api/v1/development/leads/{lead_id}/handoff-requests",
        response_model=HandoffRequestResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def post_lead_handoff_request(
        request: Request,
        response: Response,
        lead_id: UUID,
        handoff_input: HandoffRequestCreateInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=1, max_length=128),
        ],
    ) -> HandoffRequestResponse:
        validate_idempotency_key(idempotency_key)
        result, replayed = lead_service.create_handoff(
            actor=actor,
            lead_id=lead_id,
            request=handoff_input,
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.state.correlation_id),
        )
        if replayed:
            response.headers["Idempotent-Replayed"] = "true"
        return result

    @application.post(
        "/api/v1/development/handoff-requests/{handoff_id}/status",
        response_model=HandoffRequestResponse,
    )
    def post_handoff_request_status(
        request: Request,
        handoff_id: UUID,
        status_input: HandoffStatusInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> HandoffRequestResponse:
        return lead_service.set_handoff_status(
            actor=actor,
            handoff_id=handoff_id,
            request=status_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.get(
        "/api/v1/development/call-policy",
        response_model=CallPolicyResponse,
    )
    def get_call_policy(
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> CallPolicyResponse:
        return telephony_service.get_policy(actor=actor)

    @application.put(
        "/api/v1/development/call-policy",
        response_model=CallPolicyResponse,
    )
    def put_call_policy(
        request: Request,
        policy_input: CallPolicyInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> CallPolicyResponse:
        return telephony_service.replace_policy(
            actor=actor,
            request=policy_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.get(
        "/api/v1/development/inbound-numbers",
        response_model=list[InboundNumberResponse],
    )
    def get_inbound_numbers(
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> list[InboundNumberResponse]:
        return telephony_service.list_numbers(actor=actor)

    @application.post(
        "/api/v1/development/inbound-numbers",
        response_model=InboundNumberResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def post_inbound_number(
        request: Request,
        number_input: InboundNumberCreateInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> InboundNumberResponse:
        return telephony_service.create_number(
            actor=actor,
            request=number_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/inbound-numbers/{number_id}/status",
        response_model=InboundNumberResponse,
    )
    def post_inbound_number_status(
        request: Request,
        number_id: UUID,
        number_status_input: InboundNumberStatusInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> InboundNumberResponse:
        return telephony_service.set_number_status(
            actor=actor,
            number_id=number_id,
            request=number_status_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/inbound-calls",
        response_model=InboundCallActionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def post_inbound_call(
        request: Request,
        call_input: InboundCallReceiveInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> InboundCallActionResponse:
        return telephony_service.receive_call(
            actor=actor,
            request=call_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.get(
        "/api/v1/development/inbound-calls",
        response_model=InboundCallListResponse,
    )
    def get_inbound_calls(
        actor: Annotated[ActorContext, Depends(development_actor)],
        call_status: Annotated[
            InboundCallStatus | None,
            Query(alias="status"),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> InboundCallListResponse:
        return telephony_service.list_calls(
            actor=actor,
            status=call_status,
            limit=limit,
            offset=offset,
        )

    @application.get(
        "/api/v1/development/inbound-calls/{call_id}",
        response_model=InboundCallResponse,
    )
    def get_inbound_call(
        call_id: UUID,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> InboundCallResponse:
        return telephony_service.get_call(actor=actor, call_id=call_id)

    @application.post(
        "/api/v1/development/inbound-calls/{call_id}/events",
        response_model=InboundCallActionResponse,
    )
    def post_inbound_call_event(
        request: Request,
        call_id: UUID,
        event_input: InboundCallEventInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> InboundCallActionResponse:
        return telephony_service.apply_event(
            actor=actor,
            call_id=call_id,
            request=event_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/inbound-calls/{call_id}/lead",
        response_model=InboundCallActionResponse,
    )
    def post_inbound_call_lead(
        request: Request,
        call_id: UUID,
        lead_input: InboundCallLinkLeadInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
    ) -> InboundCallActionResponse:
        return telephony_service.link_lead(
            actor=actor,
            call_id=call_id,
            request=lead_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @application.post(
        "/api/v1/development/conversation-sessions/{conversation_session_id}/end",
        response_model=ConversationEndResponse,
    )
    def post_conversation_session_end(
        conversation_session_id: UUID,
        end_input: ConversationEndInput,
        actor: Annotated[ActorContext, Depends(conversation_actor)],
        service: Annotated[
            ConversationService,
            Depends(require_conversation_service),
        ],
    ) -> ConversationEndResponse:
        return service.end_session(
            actor=actor,
            conversation_session_id=conversation_session_id,
            outcome=end_input.outcome,
        )

    @application.post(
        "/api/v1/development/conversation-intakes",
        response_model=ConversationIntakeResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def post_conversation_intake(
        request: Request,
        response: Response,
        confirmation_input: ConversationIntakeConfirmationInput,
        actor: Annotated[ActorContext, Depends(conversation_actor)],
        service: Annotated[
            ConversationService,
            Depends(require_conversation_service),
        ],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=1, max_length=128),
        ],
    ) -> ConversationIntakeResponse:
        validate_idempotency_key(idempotency_key)
        result, replayed = service.confirm_intake(
            actor=actor,
            request=confirmation_input,
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.state.correlation_id),
        )
        if replayed:
            response.headers["Idempotent-Replayed"] = "true"
        return result

    return application


def default_conversation_provider(
    settings: ApiSettings,
) -> ConversationProvider | None:
    if not settings.conversation_ai_enabled:
        return None
    if settings.elevenlabs_api_key is None or settings.elevenlabs_agent_id is None:
        raise RuntimeError("conversation provider configuration is unavailable")
    return ElevenLabsConversationProvider(
        api_key=settings.elevenlabs_api_key.get_secret_value(),
        agent_id=settings.elevenlabs_agent_id,
    )


def validate_idempotency_key(idempotency_key: str) -> None:
    if idempotency_key != idempotency_key.strip():
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_FAILED",
            message="Idempotency-Key cannot contain surrounding whitespace",
        )
