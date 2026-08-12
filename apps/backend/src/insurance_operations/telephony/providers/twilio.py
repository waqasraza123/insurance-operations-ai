import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import parse_qsl

from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from insurance_operations.telephony.contracts import (
    TelephonyAdapterError,
    TransferInstruction,
    VerifiedInboundCall,
)
from insurance_operations.telephony.schemas import validate_e164

TWILIO_CALL_SID_PATTERN = re.compile(r"^CA[0-9a-fA-F]{32}$")


class TwilioCallUpdater(Protocol):
    def update_call(self, *, call_sid: str, twiml: str) -> None: ...


class TwilioSdkCallUpdater:
    def __init__(self, *, account_sid: str, auth_token: str) -> None:
        self._client = Client(account_sid, auth_token)

    def update_call(self, *, call_sid: str, twiml: str) -> None:
        try:
            self._client.calls(call_sid).update(twiml=twiml)
        except TwilioRestException as error:
            raise TelephonyAdapterError("telephony provider request failed") from error


class TwilioTelephonyAdapter:
    adapter_name = "twilio"
    adapter_version = "1"

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        inbound_webhook_url: str,
        call_updater: TwilioCallUpdater | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._inbound_webhook_url = inbound_webhook_url
        self._request_validator = RequestValidator(auth_token)
        self._call_updater = call_updater or TwilioSdkCallUpdater(
            account_sid=account_sid,
            auth_token=auth_token,
        )
        self._clock = clock or utc_now

    def verify_inbound_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> VerifiedInboundCall:
        signature = header_value(headers, "X-Twilio-Signature")
        if signature is None:
            raise TelephonyAdapterError("telephony webhook verification failed")

        content_type = header_value(headers, "Content-Type")
        if content_type is None or not content_type.lower().startswith(
            "application/x-www-form-urlencoded"
        ):
            raise TelephonyAdapterError("telephony webhook verification failed")

        try:
            raw_body = body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TelephonyAdapterError(
                "telephony webhook verification failed"
            ) from error

        pairs = parse_qsl(
            raw_body,
            keep_blank_values=True,
            strict_parsing=False,
        )
        parameters = dict(pairs)

        if not parameters or len(parameters) != len(pairs):
            raise TelephonyAdapterError("telephony webhook verification failed")

        if not self._request_validator.validate(
            self._inbound_webhook_url,
            parameters,
            signature,
        ):
            raise TelephonyAdapterError("telephony webhook verification failed")

        account_sid = required_parameter(parameters, "AccountSid")
        if account_sid != self._account_sid:
            raise TelephonyAdapterError("telephony webhook verification failed")

        call_sid = required_parameter(parameters, "CallSid")
        if TWILIO_CALL_SID_PATTERN.fullmatch(call_sid) is None:
            raise TelephonyAdapterError("telephony webhook verification failed")

        direction = parameters.get("Direction")
        if direction is not None and direction != "inbound":
            raise TelephonyAdapterError("telephony webhook verification failed")

        called_number = provider_e164(
            required_parameter(parameters, "To"),
            required=True,
        )
        if called_number is None:
            raise TelephonyAdapterError("telephony webhook verification failed")

        caller_number = provider_e164(
            parameters.get("From"),
            required=False,
        )

        occurred_at = self._clock()
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise RuntimeError("telephony adapter clock must return an aware datetime")

        return VerifiedInboundCall(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            source_call_reference=call_sid,
            called_number_e164=called_number,
            caller_number_e164=caller_number,
            occurred_at=occurred_at,
        )

    def request_transfer(
        self,
        *,
        source_call_reference: str,
        instruction: TransferInstruction,
    ) -> None:
        if TWILIO_CALL_SID_PATTERN.fullmatch(source_call_reference) is None:
            raise TelephonyAdapterError("telephony call reference is invalid")

        try:
            destination = validate_e164(instruction.destination_e164)
        except ValueError as error:
            raise TelephonyAdapterError(
                "telephony transfer destination is invalid"
            ) from error

        response = VoiceResponse()
        response.dial(
            destination,
            timeout=instruction.ring_timeout_seconds,
            answer_on_bridge=True,
        )

        self._call_updater.update_call(
            call_sid=source_call_reference,
            twiml=str(response),
        )

    def close(self) -> None:
        return None


def required_parameter(
    parameters: Mapping[str, str],
    name: str,
) -> str:
    value = parameters.get(name)
    if value is None or not value.strip():
        raise TelephonyAdapterError("telephony webhook verification failed")
    return value.strip()


def provider_e164(
    value: str | None,
    *,
    required: bool,
) -> str | None:
    if value is None or not value.strip():
        if required:
            raise TelephonyAdapterError("telephony webhook verification failed")
        return None

    normalized = value.strip()

    try:
        return validate_e164(normalized)
    except ValueError:
        if required:
            raise TelephonyAdapterError(
                "telephony webhook verification failed"
            ) from None
        return None


def header_value(
    headers: Mapping[str, str],
    name: str,
) -> str | None:
    expected = name.casefold()

    for key, value in headers.items():
        if key.casefold() == expected:
            normalized = value.strip()
            return normalized or None

    return None


def utc_now() -> datetime:
    return datetime.now(UTC)
