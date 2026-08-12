from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class NotificationDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class HandoffNotification:
    agency_id: UUID
    lead_id: UUID
    handoff_request_id: UUID
    event_type: str


class NotificationPort(Protocol):
    def send_handoff_notification(
        self,
        notification: HandoffNotification,
    ) -> None: ...

    def close(self) -> None: ...
