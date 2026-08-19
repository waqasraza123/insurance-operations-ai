import secrets

from fastapi import status

from insurance_operations.errors import ApiError
from insurance_operations.settings import ApiSettings


def require_demo_admin_token(
    settings: ApiSettings,
    supplied_token: str | None,
) -> None:
    if not settings.demo_sandbox_enabled:
        return
    expected = settings.demo_admin_token
    if (
        expected is None
        or supplied_token is None
        or not secrets.compare_digest(
            supplied_token,
            expected.get_secret_value(),
        )
    ):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="DEMO_ADMIN_AUTH_REQUIRED",
            message="Demo administrator authentication is required",
        )
