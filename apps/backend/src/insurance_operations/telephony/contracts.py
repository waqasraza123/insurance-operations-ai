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

    def close(self) -> None: ...
