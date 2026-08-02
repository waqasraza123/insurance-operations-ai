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
            database_url="postgresql://user:password@localhost/development",
            test_database_url="postgresql://user:password@localhost/test",
            database_ssl_mode=DatabaseSslMode.DISABLE,
            supabase_auth_issuer="https://example.supabase.co/auth/v1",
            supabase_auth_jwks_url=(
                "https://example.supabase.co/auth/v1/.well-known/jwks.json"
            ),
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


def test_production_authentication_endpoints_require_https() -> None:
    with pytest.raises(
        ValidationError,
        match="authentication endpoints must use HTTPS in production",
    ):
        ApiSettings(
            app_environment=RuntimeEnvironment.PRODUCTION,
            api_host="127.0.0.1",
            api_port=8000,
            database_url="postgresql://user:password@localhost/production",
            supabase_auth_issuer="http://example.supabase.co/auth/v1",
            supabase_auth_jwks_url=(
                "http://example.supabase.co/auth/v1/.well-known/jwks.json"
            ),
        )


def test_authentication_issuer_and_jwks_must_share_origin() -> None:
    with pytest.raises(
        ValidationError,
        match="authentication issuer and JWKS URL must share an origin",
    ):
        ApiSettings(
            app_environment=RuntimeEnvironment.TEST,
            api_host="127.0.0.1",
            api_port=8000,
            database_url="postgresql://user:password@localhost/development",
            test_database_url="postgresql://user:password@localhost/test",
            database_ssl_mode=DatabaseSslMode.DISABLE,
            supabase_auth_issuer="https://example.supabase.co/auth/v1",
            supabase_auth_jwks_url=(
                "https://different.supabase.co/auth/v1/.well-known/jwks.json"
            ),
        )
