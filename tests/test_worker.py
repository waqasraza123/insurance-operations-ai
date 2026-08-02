from unittest.mock import Mock, patch

from sqlalchemy.engine import Engine

from insurance_operations.settings import (
    DatabaseSslMode,
    RuntimeEnvironment,
    WorkerSettings,
)
from insurance_operations.worker import readiness


def test_worker_readiness_reports_database_identity() -> None:
    settings = WorkerSettings(
        app_environment=RuntimeEnvironment.TEST,
        worker_name="test-worker",
        database_url="postgresql://user:password@localhost/development",
        test_database_url="postgresql://user:password@localhost/test",
        database_ssl_mode=DatabaseSslMode.DISABLE,
    )
    database_engine = Mock(spec=Engine)
    connection = database_engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = 1

    with patch(
        "insurance_operations.worker.create_database_engine",
        return_value=database_engine,
    ):
        assert readiness(settings) == {
            "status": "ready",
            "service": "worker",
            "environment": "test",
            "worker": "test-worker",
            "database": "ready",
        }

    database_engine.dispose.assert_called_once()
