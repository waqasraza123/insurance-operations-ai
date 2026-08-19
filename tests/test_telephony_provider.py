from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest
from pydantic import ValidationError
from twilio.request_validator import RequestValidator

from insurance_operations.settings import RuntimeEnvironment
from insurance_operations.telephony.contracts import (
    TelephonyAdapterError,
    TransferInstruction,
)
from insurance_operations.telephony.providers.twilio import (
    TwilioTelephonyAdapter,
)
from insurance_operations.telephony.settings import TelephonyProviderSettings

ACCOUNT_SID = "AC" + ("a" * 32)
CALL_SID = "CA" + ("b" * 32)
AUTH_TOKEN = "synthetic-twilio-auth-token"
WEBHOOK_URL = "https://voice.example.test/api/v1/providers/twilio/inbound"
TRANSFER_CALLBACK_URL = (
    "https://voice.example.test/api/v1/providers/twilio/transfer-result"
)


class FakeCallUpdater:
    def __init__(self) -> None:
        self.call_sid: str | None = None
        self.twiml: str | None = None

    def update_call(self, *, call_sid: str, twiml: str) -> None:
        self.call_sid = call_sid
        self.twiml = twiml


def signed_webhook(
    parameters: dict[str, str],
    *,
    url: str = WEBHOOK_URL,
) -> tuple[dict[str, str], bytes]:
    body = urlencode(parameters).encode()

    signature = RequestValidator(AUTH_TOKEN).compute_signature(
        url,
        parameters,
    )

    return (
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature,
        },
        body,
    )


def test_twilio_adapter_verifies_and_normalizes_inbound_call() -> None:
    occurred_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

    parameters = {
        "AccountSid": ACCOUNT_SID,
        "CallSid": CALL_SID,
        "Direction": "inbound",
        "From": "+15550100100",
        "To": "+15550100200",
    }
    headers, body = signed_webhook(parameters)

    adapter = TwilioTelephonyAdapter(
        account_sid=ACCOUNT_SID,
        auth_token=AUTH_TOKEN,
        inbound_webhook_url=WEBHOOK_URL,
        transfer_callback_url=TRANSFER_CALLBACK_URL,
        clock=lambda: occurred_at,
    )

    verified = adapter.verify_inbound_webhook(
        headers=headers,
        body=body,
    )

    assert verified.adapter_name == "twilio"
    assert verified.adapter_version == "1"
    assert verified.source_call_reference == CALL_SID
    assert verified.called_number_e164 == "+15550100200"
    assert verified.caller_number_e164 == "+15550100100"
    assert verified.occurred_at == occurred_at


def test_twilio_adapter_rejects_invalid_signature() -> None:
    adapter = TwilioTelephonyAdapter(
        account_sid=ACCOUNT_SID,
        auth_token=AUTH_TOKEN,
        inbound_webhook_url=WEBHOOK_URL,
    )

    with pytest.raises(
        TelephonyAdapterError,
        match="verification failed",
    ):
        adapter.verify_inbound_webhook(
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Twilio-Signature": "invalid",
            },
            body=(
                f"AccountSid={ACCOUNT_SID}"
                f"&CallSid={CALL_SID}"
                "&Direction=inbound"
                "&From=%2B15550100100"
                "&To=%2B15550100200"
            ).encode(),
        )


def test_twilio_adapter_rejects_wrong_account() -> None:
    parameters = {
        "AccountSid": "AC" + ("c" * 32),
        "CallSid": CALL_SID,
        "Direction": "inbound",
        "From": "+15550100100",
        "To": "+15550100200",
    }
    headers, body = signed_webhook(parameters)

    adapter = TwilioTelephonyAdapter(
        account_sid=ACCOUNT_SID,
        auth_token=AUTH_TOKEN,
        inbound_webhook_url=WEBHOOK_URL,
    )

    with pytest.raises(
        TelephonyAdapterError,
        match="verification failed",
    ):
        adapter.verify_inbound_webhook(
            headers=headers,
            body=body,
        )


def test_twilio_adapter_normalizes_non_phone_caller_to_none() -> None:
    occurred_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

    parameters = {
        "AccountSid": ACCOUNT_SID,
        "CallSid": CALL_SID,
        "Direction": "inbound",
        "From": "anonymous",
        "To": "+15550100200",
    }
    headers, body = signed_webhook(parameters)

    adapter = TwilioTelephonyAdapter(
        account_sid=ACCOUNT_SID,
        auth_token=AUTH_TOKEN,
        inbound_webhook_url=WEBHOOK_URL,
        clock=lambda: occurred_at,
    )

    verified = adapter.verify_inbound_webhook(
        headers=headers,
        body=body,
    )

    assert verified.caller_number_e164 is None


def test_twilio_adapter_maps_transfer_to_active_call_update() -> None:
    updater = FakeCallUpdater()

    adapter = TwilioTelephonyAdapter(
        account_sid=ACCOUNT_SID,
        auth_token=AUTH_TOKEN,
        inbound_webhook_url=WEBHOOK_URL,
        transfer_callback_url=TRANSFER_CALLBACK_URL,
        call_updater=updater,
    )

    adapter.request_transfer(
        source_call_reference=CALL_SID,
        instruction=TransferInstruction(
            destination_e164="+15550100300",
            ring_timeout_seconds=25,
        ),
    )

    assert updater.call_sid == CALL_SID
    assert updater.twiml is not None
    assert "+15550100300" in updater.twiml
    assert "25" in updater.twiml
    assert TRANSFER_CALLBACK_URL in updater.twiml


def test_twilio_adapter_verifies_transfer_result() -> None:
    occurred_at = datetime(2026, 8, 11, 12, 3, tzinfo=UTC)
    dial_call_sid = "CA" + ("d" * 32)
    parameters = {
        "AccountSid": ACCOUNT_SID,
        "CallSid": CALL_SID,
        "DialCallSid": dial_call_sid,
        "DialCallStatus": "no-answer",
    }
    headers, body = signed_webhook(parameters, url=TRANSFER_CALLBACK_URL)
    adapter = TwilioTelephonyAdapter(
        account_sid=ACCOUNT_SID,
        auth_token=AUTH_TOKEN,
        inbound_webhook_url=WEBHOOK_URL,
        transfer_callback_url=TRANSFER_CALLBACK_URL,
        clock=lambda: occurred_at,
    )

    result = adapter.verify_transfer_callback(headers=headers, body=body)

    assert result.adapter_name == "twilio"
    assert result.source_call_reference == CALL_SID
    assert result.succeeded is False
    assert result.failure_code == "TRANSFER_NO_ANSWER"
    assert result.occurred_at == occurred_at


def test_disabled_provider_accepts_blank_environment_values() -> None:
    settings = TelephonyProviderSettings(
        app_environment=RuntimeEnvironment.DEVELOPMENT,
        telephony_provider_enabled=False,
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_inbound_webhook_url="",
    )

    assert settings.telephony_provider_enabled is False
    assert settings.twilio_account_sid is None
    assert settings.twilio_auth_token is None
    assert settings.twilio_inbound_webhook_url is None


def test_enabled_provider_requires_complete_configuration() -> None:
    with pytest.raises(
        ValidationError,
        match="telephony provider configuration is incomplete",
    ):
        TelephonyProviderSettings(
            app_environment=RuntimeEnvironment.DEVELOPMENT,
            telephony_provider_enabled=True,
        )


def test_provider_cannot_be_enabled_outside_development() -> None:
    with pytest.raises(
        ValidationError,
        match="can be enabled only in development",
    ):
        TelephonyProviderSettings(
            app_environment=RuntimeEnvironment.PRODUCTION,
            telephony_provider_enabled=True,
            twilio_account_sid=ACCOUNT_SID,
            twilio_auth_token=AUTH_TOKEN,
            twilio_inbound_webhook_url=WEBHOOK_URL,
        )
