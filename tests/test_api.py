import asyncio
from unittest.mock import MagicMock, Mock

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
        web_origin="http://localhost:3000",
        database_url="postgresql://user:password@localhost/development",
        test_database_url="postgresql://user:password@localhost/test",
        database_ssl_mode=DatabaseSslMode.DISABLE,
        conversation_ai_enabled=False,
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
    database_engine = MagicMock(spec=Engine)
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


def test_development_conversation_route_is_hidden_when_disabled() -> None:
    database_engine = Mock(spec=Engine)

    async def post_session() -> tuple[int, object]:
        transport = ASGITransport(app=create_app(api_settings(), database_engine))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/development/conversation-sessions",
                json={
                    "ai_disclosure_accepted": True,
                    "microphone_consent_granted": True,
                    "synthetic_data_acknowledged": True,
                },
            )
        return response.status_code, response.json()

    status_code, body = asyncio.run(post_session())

    assert status_code == 404
    assert isinstance(body, dict)
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "NOT_FOUND"


def test_demo_sandbox_rejects_development_route_without_admin_token() -> None:
    database_engine = Mock(spec=Engine)
    settings = ApiSettings(
        app_environment=RuntimeEnvironment.DEVELOPMENT,
        api_host="127.0.0.1",
        api_port=8000,
        web_origin="http://localhost:3000",
        database_url="postgresql://user:password@localhost/development",
        database_ssl_mode=DatabaseSslMode.DISABLE,
        conversation_ai_enabled=False,
        development_actor_user_id="00000000-0000-4000-8000-000000000002",
        demo_sandbox_enabled=True,
        demo_admin_token="synthetic-demo-admin-token-32-chars",
        demo_inbound_number_e164="+15550100100",
        demo_transfer_destination_e164="+15550100200",
    )

    async def get_settings() -> tuple[int, object]:
        transport = ASGITransport(app=create_app(settings, database_engine))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/development/receptionist-settings")
        return response.status_code, response.json()

    status_code, body = asyncio.run(get_settings())

    assert status_code == 401
    assert isinstance(body, dict)
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "DEMO_ADMIN_AUTH_REQUIRED"


def test_public_demo_route_is_hidden_when_sandbox_is_disabled() -> None:
    database_engine = Mock(spec=Engine)

    status_code, body = asyncio.run(
        get_response("/api/v1/demo/latest-phone-call", database_engine)
    )

    assert status_code == 404
    assert isinstance(body, dict)
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "NOT_FOUND"
