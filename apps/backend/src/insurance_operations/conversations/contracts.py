from dataclasses import dataclass
from typing import Literal, Protocol


class ConversationProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderSessionMetadata:
    adapter: str
    adapter_version: str
    external_session_reference: str

    def as_storage_value(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "adapter_version": self.adapter_version,
            "external_session_reference": self.external_session_reference,
        }


@dataclass(frozen=True)
class ConnectionGrant:
    transport: Literal["webrtc"]
    credential: str
    metadata: ProviderSessionMetadata


class ConversationProvider(Protocol):
    def authorize_session(self) -> ConnectionGrant: ...

    def close(self) -> None: ...
