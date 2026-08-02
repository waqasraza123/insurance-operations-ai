from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from insurance_operations.database.connection import (
    DatabaseReadinessError,
    check_database_readiness,
)
from insurance_operations.settings import ApiSettings


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["api"]
    environment: str


class ReadinessResponse(HealthResponse):
    database: Literal["ready"]


def create_app(settings: ApiSettings, database_engine: Engine) -> FastAPI:
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

    return application
