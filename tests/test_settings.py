import pytest
from pydantic import ValidationError

from insurance_operations.settings import (
    ApiSettings,
    DatabaseSslMode,
    RuntimeEnvironment,
    WorkerSettings,
)


def test_api_settings_reject_invalid_port() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 65535"):
        ApiSettings(
            app_environment=RuntimeEnvironment.TEST,
            api_host="127.0.0.1",
            api_port=70_000,
            web_origin="http://localhost:3000",
            database_url="postgresql://user:password@localhost/development",
            test_database_url="postgresql://user:password@localhost/test",
            database_ssl_mode=DatabaseSslMode.DISABLE,
            conversation_ai_enabled=False,
        )


def test_worker_settings_reject_empty_name() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        WorkerSettings(
            app_environment=RuntimeEnvironment.TEST,
            worker_name="",
            database_url="postgresql://user:password@localhost/development",
            test_database_url="postgresql://user:password@localhost/test",
            database_ssl_mode=DatabaseSslMode.DISABLE,
        )


def test_api_settings_reject_web_origin_with_a_path() -> None:
    with pytest.raises(
        ValidationError,
        match="WEB_ORIGIN must be an HTTP or HTTPS origin",
    ):
        ApiSettings(
            app_environment=RuntimeEnvironment.TEST,
            api_host="127.0.0.1",
            api_port=8000,
            web_origin="https://example.test/application",
            database_url="postgresql://user:password@localhost/development",
            test_database_url="postgresql://user:password@localhost/test",
            database_ssl_mode=DatabaseSslMode.DISABLE,
            conversation_ai_enabled=False,
        )


def test_conversation_ai_cannot_be_enabled_outside_development() -> None:
    with pytest.raises(
        ValidationError,
        match="conversation AI can be enabled only in development",
    ):
        ApiSettings(
            app_environment=RuntimeEnvironment.TEST,
            api_host="127.0.0.1",
            api_port=8000,
            database_url="postgresql://user:password@localhost/development",
            test_database_url="postgresql://user:password@localhost/test",
            database_ssl_mode=DatabaseSslMode.DISABLE,
            conversation_ai_enabled=True,
        )


def test_enabled_conversation_ai_requires_privacy_attestation() -> None:
    with pytest.raises(
        ValidationError,
        match="audio saving and zero-day retention must be confirmed",
    ):
        ApiSettings(
            app_environment=RuntimeEnvironment.DEVELOPMENT,
            api_host="127.0.0.1",
            api_port=8000,
            database_url="postgresql://user:password@localhost/development",
            database_ssl_mode=DatabaseSslMode.DISABLE,
            conversation_ai_enabled=True,
            development_actor_user_id="00000000-0000-4000-8000-000000000002",
            elevenlabs_api_key="test-secret",
            elevenlabs_agent_id="agent_test",
            elevenlabs_privacy_confirmed=False,
        )


def test_enabled_conversation_ai_accepts_complete_configuration() -> None:
    settings = ApiSettings(
        app_environment=RuntimeEnvironment.DEVELOPMENT,
        api_host="127.0.0.1",
        api_port=8000,
        database_url="postgresql://user:password@localhost/development",
        database_ssl_mode=DatabaseSslMode.DISABLE,
        conversation_ai_enabled=True,
        development_actor_user_id="00000000-0000-4000-8000-000000000002",
        elevenlabs_api_key="test-secret",
        elevenlabs_agent_id="agent_test",
        elevenlabs_privacy_confirmed=True,
    )

    assert settings.conversation_max_duration_seconds == 180
    assert settings.conversation_daily_session_limit == 10


def test_demo_sandbox_requires_a_strong_admin_token() -> None:
    with pytest.raises(
        ValidationError,
        match="DEMO_ADMIN_TOKEN must contain at least 32 characters",
    ):
        ApiSettings(
            app_environment=RuntimeEnvironment.DEVELOPMENT,
            api_host="127.0.0.1",
            api_port=8000,
            database_url="postgresql://user:password@localhost/development",
            database_ssl_mode=DatabaseSslMode.DISABLE,
            development_actor_user_id="00000000-0000-4000-8000-000000000002",
            demo_sandbox_enabled=True,
            demo_admin_token="too-short",
            demo_inbound_number_e164="+15550100100",
            demo_transfer_destination_e164="+15550100200",
        )


def test_demo_sandbox_accepts_complete_development_configuration() -> None:
    settings = ApiSettings(
        app_environment=RuntimeEnvironment.DEVELOPMENT,
        api_host="127.0.0.1",
        api_port=8000,
        database_url="postgresql://user:password@localhost/development",
        database_ssl_mode=DatabaseSslMode.DISABLE,
        development_actor_user_id="00000000-0000-4000-8000-000000000002",
        demo_sandbox_enabled=True,
        demo_admin_token="synthetic-demo-admin-token-32-chars",
        demo_inbound_number_e164="+15550100100",
        demo_transfer_destination_e164="+15550100200",
    )

    assert settings.demo_sandbox_enabled is True
    assert settings.demo_result_ttl_minutes == 15
