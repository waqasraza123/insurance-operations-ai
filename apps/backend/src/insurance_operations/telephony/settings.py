import re
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator

from insurance_operations.settings import CommonSettings, RuntimeEnvironment

TWILIO_ACCOUNT_SID_PATTERN = re.compile(r"^AC[0-9a-fA-F]{32}$")


class TelephonyProviderSettings(CommonSettings):
    telephony_provider_enabled: bool = False
    development_actor_user_id: UUID | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_inbound_webhook_url: str | None = None
    twilio_transfer_callback_url: str | None = None
    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_phone_agent_id: str | None = None
    elevenlabs_phone_tool_secret: SecretStr | None = None
    elevenlabs_post_call_webhook_secret: SecretStr | None = None
    elevenlabs_privacy_confirmed: bool = False
    phone_max_duration_seconds: int = Field(default=180, ge=1, le=180)
    phone_confirmation_window_minutes: int = Field(default=30, ge=5, le=60)

    @field_validator(
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_inbound_webhook_url",
        "twilio_transfer_callback_url",
        "elevenlabs_api_key",
        "elevenlabs_phone_agent_id",
        "elevenlabs_phone_tool_secret",
        "elevenlabs_post_call_webhook_secret",
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

    @field_validator(
        "twilio_inbound_webhook_url",
        "twilio_transfer_callback_url",
    )
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
            raise ValueError("Twilio webhook URLs must use valid HTTPS URLs")
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

        if self.twilio_transfer_callback_url is None:
            missing.append("TWILIO_TRANSFER_CALLBACK_URL")
        if self.development_actor_user_id is None:
            missing.append("DEVELOPMENT_ACTOR_USER_ID")
        if (
            self.elevenlabs_api_key is None
            or not self.elevenlabs_api_key.get_secret_value()
        ):
            missing.append("ELEVENLABS_API_KEY")
        if self.elevenlabs_phone_agent_id is None:
            missing.append("ELEVENLABS_PHONE_AGENT_ID")
        if (
            self.elevenlabs_phone_tool_secret is None
            or not self.elevenlabs_phone_tool_secret.get_secret_value()
        ):
            missing.append("ELEVENLABS_PHONE_TOOL_SECRET")
        if (
            self.elevenlabs_post_call_webhook_secret is None
            or not self.elevenlabs_post_call_webhook_secret.get_secret_value()
        ):
            missing.append("ELEVENLABS_POST_CALL_WEBHOOK_SECRET")
        if not self.elevenlabs_privacy_confirmed:
            missing.append("ELEVENLABS_PRIVACY_CONFIRMED")

        if missing:
            raise ValueError(
                "telephony provider configuration is incomplete: " + ", ".join(missing)
            )

        return self
