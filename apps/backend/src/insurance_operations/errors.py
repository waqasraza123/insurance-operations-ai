from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any]
    correlation_id: str


class ApiErrorResponse(BaseModel):
    error: ApiErrorDetail


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers


async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    response = ApiErrorResponse(
        error=ApiErrorDetail(
            code=error.code,
            message=error.message,
            details=error.details,
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(
        status_code=error.status_code,
        content=response.model_dump(mode="json"),
        headers=error.headers,
    )
