import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from xml.etree import ElementTree

import httpx

from insurance_operations.telephony.contracts import TelephonyAdapterError

ELEVENLABS_API_BASE_URL = "https://api.elevenlabs.io"
MAX_TWIML_BYTES = 65_536
MAX_WEBHOOK_BYTES = 1_000_000
WEBHOOK_TOLERANCE_SECONDS = 300


@dataclass(frozen=True)
class PhoneCallRegistration:
    inbound_call_id: str
    from_number: str
    to_number: str
    maximum_duration_seconds: int


class ElevenLabsPhoneProvider:
    def __init__(
        self,
        *,
        api_key: str,
        agent_id: str,
        post_call_webhook_secret: str,
        client: httpx.Client | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._api_key = api_key
        self._agent_id = agent_id
        self._post_call_webhook_secret = post_call_webhook_secret.encode("utf-8")
        self._client = client
        self._clock = clock or time.time

    def register_inbound_call(self, registration: PhoneCallRegistration) -> str:
        owns_client = self._client is None
        client = self._client or httpx.Client(
            base_url=ELEVENLABS_API_BASE_URL,
            timeout=httpx.Timeout(10),
        )
        try:
            response = client.post(
                "/v1/convai/twilio/register-call",
                headers={"xi-api-key": self._api_key},
                json={
                    "agent_id": self._agent_id,
                    "from_number": registration.from_number,
                    "to_number": registration.to_number,
                    "direction": "inbound",
                    "conversation_initiation_client_data": {
                        "dynamic_variables": {
                            "phone_inbound_call_id": registration.inbound_call_id,
                            "phone_max_duration_seconds": (
                                registration.maximum_duration_seconds
                            ),
                        }
                    },
                },
            )
            response.raise_for_status()
            twiml = response_text(response)
            validate_twiml(twiml)
            return twiml
        except (httpx.HTTPError, ValueError, ElementTree.ParseError) as error:
            raise TelephonyAdapterError(
                "phone conversation provider registration failed"
            ) from error
        finally:
            if owns_client:
                client.close()

    def verify_post_call_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> dict[str, object]:
        if len(body) > MAX_WEBHOOK_BYTES:
            raise TelephonyAdapterError("phone provider webhook verification failed")

        signature_header = header_value(headers, "ElevenLabs-Signature")
        if signature_header is None:
            raise TelephonyAdapterError("phone provider webhook verification failed")

        timestamp, supplied_signature = parse_signature(signature_header)
        if abs(self._clock() - timestamp) > WEBHOOK_TOLERANCE_SECONDS:
            raise TelephonyAdapterError("phone provider webhook verification failed")

        signed_payload = str(timestamp).encode("ascii") + b"." + body
        expected_signature = hmac.new(
            self._post_call_webhook_secret,
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise TelephonyAdapterError("phone provider webhook verification failed")

        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TelephonyAdapterError(
                "phone provider webhook verification failed"
            ) from error
        data = payload.get("data") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or not isinstance(data, dict)
            or data.get("agent_id") != self._agent_id
        ):
            raise TelephonyAdapterError("phone provider webhook verification failed")
        return payload


def response_text(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").casefold()
    if "json" in content_type:
        value = response.json()
        if not isinstance(value, str):
            raise ValueError("register-call response must be a string")
        return value
    return response.text


def validate_twiml(value: str) -> None:
    encoded = value.encode("utf-8")
    if not encoded or len(encoded) > MAX_TWIML_BYTES:
        raise ValueError("register-call TwiML is outside allowed bounds")
    upper_value = value.upper()
    if "<!DOCTYPE" in upper_value or "<!ENTITY" in upper_value:
        raise ValueError("register-call TwiML contains a prohibited declaration")
    root = ElementTree.fromstring(value)
    if root.tag.rsplit("}", 1)[-1] != "Response":
        raise ValueError("register-call TwiML root must be Response")
    element_names = {element.tag.rsplit("}", 1)[-1] for element in root.iter()}
    if "Record" in element_names or "Stream" not in element_names:
        raise ValueError("register-call TwiML violates the phone audio contract")


def parse_signature(value: str) -> tuple[int, str]:
    parts: dict[str, str] = {}
    for item in value.split(","):
        key, separator, part_value = item.strip().partition("=")
        if not separator or key in parts:
            raise TelephonyAdapterError("phone provider webhook verification failed")
        parts[key] = part_value
    try:
        timestamp = int(parts["t"])
        signature = parts["v0"]
    except (KeyError, ValueError) as error:
        raise TelephonyAdapterError(
            "phone provider webhook verification failed"
        ) from error
    if timestamp < 0 or len(signature) != 64:
        raise TelephonyAdapterError("phone provider webhook verification failed")
    return timestamp, signature


def header_value(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    for key, value in headers.items():
        if key.casefold() == expected:
            normalized = value.strip()
            return normalized or None
    return None
