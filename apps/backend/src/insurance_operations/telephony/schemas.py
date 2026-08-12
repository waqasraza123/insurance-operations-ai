import re
from datetime import datetime, time
from enum import StrEnum
from itertools import pairwise
from typing import Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from insurance_operations.database.models.telephony import (
    InboundCallStatus,
    InboundNumberStatus,
)


class AvailabilityWindow(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_local: time
    end_local: time

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.start_local >= self.end_local:
            raise ValueError("availability windows cannot cross midnight")
        return self


class CallPolicyContent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    inbound_enabled: bool
    timezone: str = Field(min_length=1, max_length=100)
    availability_windows: list[AvailabilityWindow] = Field(max_length=40)
    transfer_enabled: bool
    transfer_destination_e164: str | None = None
    transfer_ring_timeout_seconds: int = Field(ge=10, le=60)
    max_concurrent_calls: int = Field(ge=1, le=20)
    daily_call_limit: int = Field(ge=1, le=1_000)
    callback_fallback_enabled: bool
    after_hours_message: str = Field(min_length=1, max_length=600)
    unavailable_message: str = Field(min_length=1, max_length=600)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return value

    @field_validator("transfer_destination_e164")
    @classmethod
    def validate_transfer_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_e164(value)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.transfer_enabled and self.transfer_destination_e164 is None:
            raise ValueError(
                "transfer destination is required when transfer is enabled"
            )
        windows_by_day: dict[int, list[AvailabilityWindow]] = {}
        for window in self.availability_windows:
            windows_by_day.setdefault(window.weekday, []).append(window)
        for windows in windows_by_day.values():
            ordered = sorted(windows, key=lambda window: window.start_local)
            if any(
                current.start_local < previous.end_local
                for previous, current in pairwise(ordered)
            ):
                raise ValueError("availability windows cannot overlap")
        return self


class CallPolicyInput(CallPolicyContent):
    expected_row_version: int = Field(ge=0)


class CallPolicyResponse(CallPolicyContent):
    id: UUID
    agency_id: UUID
    row_version: int
    created_at: datetime
    updated_at: datetime


class InboundNumberCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    phone_number_e164: str
    label: str = Field(min_length=1, max_length=120)
    status: InboundNumberStatus = InboundNumberStatus.INACTIVE

    @field_validator("phone_number_e164")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        return validate_e164(value)


class InboundNumberStatusInput(BaseModel):
    status: InboundNumberStatus
    expected_row_version: int = Field(ge=1)


class InboundNumberResponse(BaseModel):
    id: UUID
    agency_id: UUID
    phone_number_e164: str
    label: str
    status: InboundNumberStatus
    row_version: int
    created_at: datetime
    updated_at: datetime


class InboundCallReceiveInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    adapter_name: str = Field(min_length=1, max_length=80)
    adapter_version: str = Field(min_length=1, max_length=40)
    source_call_reference: str = Field(min_length=1, max_length=200)
    called_number_e164: str
    caller_number_e164: str | None = None
    occurred_at: datetime

    @field_validator("called_number_e164")
    @classmethod
    def validate_called_number(cls, value: str) -> str:
        return validate_e164(value)

    @field_validator("caller_number_e164")
    @classmethod
    def validate_caller_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_e164(value)

    @field_validator("occurred_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class InboundCallEventType(StrEnum):
    ANSWERED = "ANSWERED"
    TRANSFER_REQUESTED = "TRANSFER_REQUESTED"
    TRANSFER_SUCCEEDED = "TRANSFER_SUCCEEDED"
    TRANSFER_FAILED = "TRANSFER_FAILED"
    CALL_ENDED = "CALL_ENDED"
    PROVIDER_FAILED = "PROVIDER_FAILED"


class InboundCallEventInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    event_key: str = Field(min_length=1, max_length=200)
    event_type: InboundCallEventType
    occurred_at: datetime
    failure_code: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("occurred_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_failure_code(self) -> Self:
        if (
            self.event_type is not InboundCallEventType.PROVIDER_FAILED
            and self.failure_code is not None
        ):
            raise ValueError("failure_code is only valid for PROVIDER_FAILED")
        return self


class InboundCallLinkLeadInput(BaseModel):
    lead_id: UUID
    expected_row_version: int = Field(ge=1)


class CallAction(StrEnum):
    ANSWER_AI = "ANSWER_AI"
    CONTINUE_AI = "CONTINUE_AI"
    TRANSFER = "TRANSFER"
    COLLECT_CALLBACK = "COLLECT_CALLBACK"
    CALLBACK_CONFIRMED = "CALLBACK_CONFIRMED"
    END = "END"


class InboundCallResponse(BaseModel):
    id: UUID
    agency_id: UUID
    inbound_number_id: UUID
    lead_id: UUID | None
    status: InboundCallStatus
    caller_number_e164: str | None
    adapter_name: str
    received_at: datetime
    answered_at: datetime | None
    ended_at: datetime | None
    failure_code: str | None
    row_version: int
    created_at: datetime
    updated_at: datetime


class InboundCallActionResponse(BaseModel):
    call: InboundCallResponse
    action: CallAction
    message: str | None = None
    transfer_destination_e164: str | None = None
    transfer_ring_timeout_seconds: int | None = None
    replayed: bool = False


class InboundCallListResponse(BaseModel):
    items: list[InboundCallResponse]
    total: int
    limit: int
    offset: int


def validate_e164(value: str) -> str:
    if re.fullmatch(r"\+[1-9][0-9]{7,14}", value) is None:
        raise ValueError("phone number must use E.164 format")
    return value
