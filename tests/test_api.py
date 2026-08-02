import asyncio

from httpx import ASGITransport, AsyncClient
from insurance_operations.application import create_app
from insurance_operations.settings import ApiSettings, RuntimeEnvironment


async def get_health_response(settings: ApiSettings) -> tuple[int, dict[str, str]]:
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    return response.status_code, response.json()


def test_health_reports_api_readiness() -> None:
    settings = ApiSettings(
        app_environment=RuntimeEnvironment.TEST,
        api_host="127.0.0.1",
        api_port=8000,
    )

    status_code, body = asyncio.run(get_health_response(settings))

    assert status_code == 200
    assert body == {
        "status": "ok",
        "service": "api",
        "environment": "test",
    }
