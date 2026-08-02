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
