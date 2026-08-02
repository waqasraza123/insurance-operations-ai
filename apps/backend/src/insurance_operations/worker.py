import argparse
import json
import logging
import signal
from threading import Event
from types import FrameType

from pydantic import ValidationError

from insurance_operations.settings import WorkerSettings


def readiness(settings: WorkerSettings) -> dict[str, str]:
    return {
        "status": "ready",
        "service": "worker",
        "environment": settings.app_environment,
        "worker": settings.worker_name,
    }


def run(settings: WorkerSettings) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger(__name__)
    stopped = Event()

    def request_shutdown(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        stopped.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    logger.info("worker ready: %s", settings.worker_name)
    stopped.wait()
    logger.info("worker stopped: %s", settings.worker_name)


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

    if arguments.check:
        print(json.dumps(readiness(settings), sort_keys=True))
        return

    run(settings)


if __name__ == "__main__":
    main()
