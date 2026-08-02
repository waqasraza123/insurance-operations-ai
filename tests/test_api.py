import asyncio
from unittest.mock import Mock

from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from insurance_operations.application import create_app
from insurance_operations.settings import (
    ApiSettings,
    DatabaseSslMode,
    RuntimeEnvironment,
)


def api_settings() -> ApiSettings:
    return ApiSettings(
        app_environment=RuntimeEnvironment.TEST,
        api_host="127.0.0.1",
        api_port=8000,
        database_url="postgresql://user:password@localhost/development",
        test_database_url="postgresql://user:password@localhost/test",
        database_ssl_mode=DatabaseSslMode.DISABLE,
    )


async def get_response(path: str, database_engine: Engine) -> tuple[int, object]:
    transport = ASGITransport(app=create_app(api_settings(), database_engine))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)
    return response.status_code, response.json()


def test_health_reports_api_liveness() -> None:
    database_engine = Mock(spec=Engine)

    status_code, body = asyncio.run(get_response("/health", database_engine))

    assert status_code == 200
    assert body == {
        "status": "ok",
        "service": "api",
        "environment": "test",
    }


def test_ready_reports_database_readiness() -> None:
    database_engine = Mock(spec=Engine)
    connection = database_engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = 1

    status_code, body = asyncio.run(get_response("/ready", database_engine))

    assert status_code == 200
    assert body == {
        "status": "ok",
        "service": "api",
        "environment": "test",
        "database": "ready",
    }


def test_ready_hides_database_failure_details() -> None:
    database_engine = Mock(spec=Engine)
    database_engine.connect.side_effect = SQLAlchemyError("sensitive provider error")

    status_code, body = asyncio.run(get_response("/ready", database_engine))

    assert status_code == 503
    assert body == {"detail": "database unavailable"}
