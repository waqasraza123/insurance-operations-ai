from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from insurance_operations.settings import ApiSettings


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["api"]
    environment: str


def create_app(settings: ApiSettings) -> FastAPI:
    application = FastAPI(
        title="Insurance Operations AI API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="api",
            environment=settings.app_environment,
        )

    return application
