import hashlib
import hmac
import json

import httpx
import pytest

from insurance_operations.telephony.contracts import TelephonyAdapterError
from insurance_operations.telephony.providers.elevenlabs import (
    ElevenLabsPhoneProvider,
    PhoneCallRegistration,
)


def test_register_call_returns_validated_twiml_without_exposing_key() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Connect><Stream url="wss://example.test/phone" />'
                "</Connect></Response>"
            ),
        )

    client = httpx.Client(
        base_url="https://api.elevenlabs.io",
        transport=httpx.MockTransport(handler),
    )
    provider = ElevenLabsPhoneProvider(
        api_key="synthetic-api-key",
        agent_id="synthetic-phone-agent",
        post_call_webhook_secret="synthetic-webhook-secret",
        client=client,
    )

    twiml = provider.register_inbound_call(
        PhoneCallRegistration(
            inbound_call_id="00000000-0000-4000-8000-000000000010",
            from_number="+15550100100",
            to_number="+15550100200",
            maximum_duration_seconds=180,
        )
    )

    assert captured_request is not None
    assert captured_request.url.path == "/v1/convai/twilio/register-call"
    assert captured_request.headers["xi-api-key"] == "synthetic-api-key"
    request_body = json.loads(captured_request.content)
    assert request_body["agent_id"] == "synthetic-phone-agent"
    assert request_body["direction"] == "inbound"
    assert "synthetic-api-key" not in twiml
    assert twiml.startswith("<?xml")


def test_register_call_rejects_non_twiml_response() -> None:
    client = httpx.Client(
        base_url="https://api.elevenlabs.io",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="not XML")
        ),
    )
    provider = ElevenLabsPhoneProvider(
        api_key="synthetic-api-key",
        agent_id="synthetic-phone-agent",
        post_call_webhook_secret="synthetic-webhook-secret",
        client=client,
    )

    with pytest.raises(TelephonyAdapterError, match="registration failed"):
        provider.register_inbound_call(
            PhoneCallRegistration(
                inbound_call_id="00000000-0000-4000-8000-000000000010",
                from_number="+15550100100",
                to_number="+15550100200",
                maximum_duration_seconds=180,
            )
        )


def test_post_call_webhook_requires_valid_fresh_hmac() -> None:
    timestamp = 1_786_550_400
    secret = "synthetic-webhook-secret"
    body = json.dumps(
        {
            "type": "post_call_transcription",
            "event_timestamp": timestamp,
            "data": {
                "agent_id": "synthetic-phone-agent",
                "conversation_id": "conv_synthetic",
            },
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(
        secret.encode(),
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    provider = ElevenLabsPhoneProvider(
        api_key="synthetic-api-key",
        agent_id="synthetic-phone-agent",
        post_call_webhook_secret=secret,
        clock=lambda: float(timestamp),
    )

    payload = provider.verify_post_call_webhook(
        headers={"ElevenLabs-Signature": f"t={timestamp},v0={signature}"},
        body=body,
    )

    assert payload["type"] == "post_call_transcription"

    with pytest.raises(TelephonyAdapterError, match="verification failed"):
        provider.verify_post_call_webhook(
            headers={"ElevenLabs-Signature": f"t={timestamp},v0={'0' * 64}"},
            body=body,
        )
