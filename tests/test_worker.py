from insurance_operations.settings import RuntimeEnvironment, WorkerSettings
from insurance_operations.worker import readiness


def test_worker_readiness_reports_runtime_identity() -> None:
    settings = WorkerSettings(
        app_environment=RuntimeEnvironment.TEST,
        worker_name="test-worker",
    )

    assert readiness(settings) == {
        "status": "ready",
        "service": "worker",
        "environment": "test",
        "worker": "test-worker",
    }
