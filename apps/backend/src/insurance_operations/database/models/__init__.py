from dataclasses import dataclass

from insurance_operations.database.models.base import Base
from insurance_operations.database.models.conversation import (
    ConversationIntake,
    ConversationSession,
)
from insurance_operations.database.models.customer import Customer
from insurance_operations.database.models.identity import (
    Agency,
    AgencyMembership,
    AppUser,
)
from insurance_operations.database.models.operations import (
    AuditEvent,
    IdempotencyRecord,
)


@dataclass(frozen=True)
class TableOwnership:
    module: str
    agency_column: str | None


TABLE_OWNERSHIP = {
    "agencies": TableOwnership(module="identity", agency_column=None),
    "app_users": TableOwnership(module="identity", agency_column=None),
    "agency_memberships": TableOwnership(
        module="identity",
        agency_column="agency_id",
    ),
    "customers": TableOwnership(module="customers", agency_column="agency_id"),
    "conversation_sessions": TableOwnership(
        module="conversations",
        agency_column="agency_id",
    ),
    "conversation_intakes": TableOwnership(
        module="conversations",
        agency_column="agency_id",
    ),
    "audit_events": TableOwnership(module="audit", agency_column="agency_id"),
    "idempotency_records": TableOwnership(
        module="idempotency",
        agency_column="agency_id",
    ),
}

__all__ = [
    "Agency",
    "AgencyMembership",
    "AppUser",
    "AuditEvent",
    "Base",
    "ConversationIntake",
    "ConversationSession",
    "Customer",
    "IdempotencyRecord",
    "TABLE_OWNERSHIP",
    "TableOwnership",
]
