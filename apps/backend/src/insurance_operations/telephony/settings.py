import re
from typing import Self
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator

from insurance_operations.settings import CommonSettings, RuntimeEnvironment

TWILIO_ACCOUNT_SID_PATTERN = re.compile(r"^AC[0-9a-fA-F]{32}$")


class TelephonyProviderSettings(CommonSettings):
    telephony_provider_enabled: bool = False
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_inbound_webhook_url: str | None = None

    @field_validator(
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_inbound_webhook_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_value(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("twilio_account_sid")
    @classmethod
    def validate_twilio_account_sid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if TWILIO_ACCOUNT_SID_PATTERN.fullmatch(value) is None:
            raise ValueError("TWILIO_ACCOUNT_SID must be a valid Twilio account SID")
        return value

    @field_validator("twilio_inbound_webhook_url")
    @classmethod
    def validate_twilio_webhook_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("TWILIO_INBOUND_WEBHOOK_URL must be an HTTPS webhook URL")
        return value

    @model_validator(mode="after")
    def validate_enabled_provider(self) -> Self:
        if not self.telephony_provider_enabled:
            return self

        if self.app_environment is not RuntimeEnvironment.DEVELOPMENT:
            raise ValueError(
                "telephony provider integration can be enabled only in development"
            )

        missing: list[str] = []

        if self.twilio_account_sid is None:
            missing.append("TWILIO_ACCOUNT_SID")

        if (
            self.twilio_auth_token is None
            or not self.twilio_auth_token.get_secret_value()
        ):
            missing.append("TWILIO_AUTH_TOKEN")

        if self.twilio_inbound_webhook_url is None:
            missing.append("TWILIO_INBOUND_WEBHOOK_URL")

        if missing:
            raise ValueError(
                "telephony provider configuration is incomplete: " + ", ".join(missing)
            )

        return self
