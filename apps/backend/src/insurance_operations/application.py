from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
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
from insurance_operations.errors import ApiError, api_error_handler
from insurance_operations.settings import ApiSettings, RuntimeEnvironment


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
        allow_methods=["GET", "POST"],
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

    def development_actor(
        service: Annotated[
            ConversationService,
            Depends(require_conversation_service),
        ],
    ) -> ActorContext:
        del service
        if settings.development_actor_user_id is None:
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
        actor: Annotated[ActorContext, Depends(development_actor)],
        service: Annotated[
            ConversationService,
            Depends(require_conversation_service),
        ],
    ) -> ConversationSessionResponse:
        return service.authorize_session(actor=actor, request=conversation_input)

    @application.post(
        "/api/v1/development/conversation-sessions/{conversation_session_id}/end",
        response_model=ConversationEndResponse,
    )
    def post_conversation_session_end(
        conversation_session_id: UUID,
        end_input: ConversationEndInput,
        actor: Annotated[ActorContext, Depends(development_actor)],
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
        actor: Annotated[ActorContext, Depends(development_actor)],
        service: Annotated[
            ConversationService,
            Depends(require_conversation_service),
        ],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=1, max_length=128),
        ],
    ) -> ConversationIntakeResponse:
        if idempotency_key != idempotency_key.strip():
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="VALIDATION_FAILED",
                message="Idempotency-Key cannot contain surrounding whitespace",
            )
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
