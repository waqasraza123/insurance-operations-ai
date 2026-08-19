from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class TelephonyAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedInboundCall:
    adapter_name: str
    adapter_version: str
    source_call_reference: str
    called_number_e164: str
    caller_number_e164: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class TransferInstruction:
    destination_e164: str
    ring_timeout_seconds: int


@dataclass(frozen=True)
class VerifiedTransferResult:
    adapter_name: str
    source_call_reference: str
    event_key: str
    succeeded: bool
    occurred_at: datetime
    failure_code: str | None = None


class TelephonyAdapter(Protocol):
    def verify_inbound_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> VerifiedInboundCall: ...

    def request_transfer(
        self,
        *,
        source_call_reference: str,
        instruction: TransferInstruction,
    ) -> None: ...

    def verify_transfer_callback(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> VerifiedTransferResult: ...

    def close(self) -> None: ...
