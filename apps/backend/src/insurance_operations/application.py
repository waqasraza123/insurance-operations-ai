from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint

from insurance_operations.customers import (
    CustomerCreateInput,
    CustomerCreateResponse,
    create_customer,
)
from insurance_operations.database.connection import (
    DatabaseReadinessError,
    check_database_readiness,
)
from insurance_operations.errors import ApiError, api_error_handler
from insurance_operations.identity import (
    AccessTokenVerificationError,
    AccessTokenVerifier,
    ActorContext,
    ActorResolutionError,
    SupabaseAccessTokenVerifier,
    resolve_actor,
)
from insurance_operations.settings import ApiSettings


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["api"]
    environment: str


class ReadinessResponse(HealthResponse):
    database: Literal["ready"]


class ActorResponse(BaseModel):
    app_user_id: UUID
    display_name: str
    agency_id: UUID
    agency_name: str
    agency_environment: str


def create_app(
    settings: ApiSettings,
    database_engine: Engine,
    access_token_verifier: AccessTokenVerifier | None = None,
) -> FastAPI:
    session_factory = sessionmaker(
        bind=database_engine,
        class_=Session,
        expire_on_commit=False,
    )
    token_verifier = access_token_verifier or SupabaseAccessTokenVerifier(settings)
    bearer_scheme = HTTPBearer(auto_error=False)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        yield
        database_engine.dispose()

    application = FastAPI(
        title="Insurance Operations AI API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
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
            correlation_id = (
                UUID(raw_correlation_id) if raw_correlation_id else uuid4()
            )
        except ValueError:
            correlation_id = uuid4()
        request.state.correlation_id = str(correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = str(correlation_id)
        return response

    def authenticated_actor(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(bearer_scheme),
        ],
    ) -> ActorContext:
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="UNAUTHENTICATED",
                message="A valid bearer token is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            identity = token_verifier.verify(credentials.credentials)
        except AccessTokenVerificationError as error:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="UNAUTHENTICATED",
                message="A valid bearer token is required",
                headers={"WWW-Authenticate": "Bearer"},
            ) from error

        try:
            with session_factory() as session:
                return resolve_actor(session, identity)
        except ActorResolutionError as error:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="AGENCY_ACCESS_DENIED",
                message="An active agency membership is required",
            ) from error

    def database_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

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

    @application.get("/api/v1/me", response_model=ActorResponse)
    def get_current_actor(
        actor: Annotated[ActorContext, Depends(authenticated_actor)],
    ) -> ActorResponse:
        return ActorResponse(
            app_user_id=actor.app_user_id,
            display_name=actor.display_name,
            agency_id=actor.agency_id,
            agency_name=actor.agency_name,
            agency_environment=actor.agency_environment,
        )

    @application.post(
        "/api/v1/customers",
        response_model=CustomerCreateResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def post_customer(
        request: Request,
        response: Response,
        customer_input: CustomerCreateInput,
        actor: Annotated[ActorContext, Depends(authenticated_actor)],
        session: Annotated[Session, Depends(database_session)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=1, max_length=128),
        ],
    ) -> CustomerCreateResponse:
        if idempotency_key != idempotency_key.strip():
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="VALIDATION_FAILED",
                message="Idempotency-Key cannot contain surrounding whitespace",
            )
        result, replayed = create_customer(
            session,
            actor=actor,
            request=customer_input,
            idempotency_key=idempotency_key,
            correlation_id=UUID(request.state.correlation_id),
            retention_hours=settings.idempotency_retention_hours,
        )
        response.headers["ETag"] = f'"rv:{result.customer.row_version}"'
        if replayed:
            response.headers["Idempotent-Replayed"] = "true"
        return result

    return application
