import argparse
import json
import logging
import signal
from threading import Event
from types import FrameType

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from insurance_operations.database.connection import (
    DatabaseReadinessError,
    check_database_readiness,
    create_database_engine,
)
from insurance_operations.settings import WorkerSettings


def readiness(settings: WorkerSettings) -> dict[str, str]:
    database_engine = create_database_engine(
        settings, service_name=settings.worker_name
    )
    try:
        check_database_readiness(database_engine)
    finally:
        database_engine.dispose()

    return {
        "status": "ready",
        "service": "worker",
        "environment": settings.app_environment,
        "worker": settings.worker_name,
        "database": "ready",
    }


def run(settings: WorkerSettings) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger(__name__)
    stopped = Event()
    database_engine = create_database_engine(
        settings, service_name=settings.worker_name
    )

    def request_shutdown(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        stopped.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    try:
        check_database_readiness(database_engine)
        logger.info("worker ready: %s", settings.worker_name)
        stopped.wait()
        logger.info("worker stopped: %s", settings.worker_name)
    finally:
        database_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="insurance-operations-worker")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate configuration and exit",
    )
    arguments = parser.parse_args()

    try:
        settings = WorkerSettings()
    except ValidationError as error:
        parser.exit(2, f"configuration error:\n{error}\n")

    try:
        if arguments.check:
            result = readiness(settings)
            print(json.dumps(result, sort_keys=True))
            return

        run(settings)
    except (DatabaseReadinessError, SQLAlchemyError):
        parser.exit(1, "readiness error: database unavailable\n")


if __name__ == "__main__":
    main()
