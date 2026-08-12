from datetime import UTC, datetime

from insurance_operations.telephony.service import is_staff_available


def test_staff_availability_uses_policy_timezone_and_windows() -> None:
    snapshot: dict[str, object] = {
        "timezone": "America/New_York",
        "availability_windows": [
            {"weekday": 0, "start_local": "09:00", "end_local": "17:00"}
        ],
    }

    assert is_staff_available(
        snapshot,
        datetime(2026, 8, 10, 15, 0, tzinfo=UTC),
    )
    assert not is_staff_available(
        snapshot,
        datetime(2026, 8, 10, 23, 0, tzinfo=UTC),
    )
