from dataclasses import dataclass

from insurance_operations.database.models.approved_faq import (
    AgencyApprovedFaq,
    ApprovedFaqStatus,
)
from insurance_operations.database.models.base import Base
from insurance_operations.database.models.conversation import (
    ConversationChannel,
    ConversationIntake,
    ConversationIntakeConfirmationReceipt,
    ConversationSession,
)
from insurance_operations.database.models.customer import Customer
from insurance_operations.database.models.identity import (
    Agency,
    AgencyMembership,
    AppUser,
)
from insurance_operations.database.models.lead import (
    AgencyLead,
    HandoffContactMethod,
    HandoffRequestKind,
    HandoffStatus,
    LeadHandoffRequest,
    LeadStatus,
    LeadUrgency,
)
from insurance_operations.database.models.operations import (
    AuditEvent,
    IdempotencyRecord,
)
from insurance_operations.database.models.receptionist import (
    AgencyReceptionistSettings,
)
from insurance_operations.database.models.telephony import (
    AgencyCallPolicy,
    AgencyInboundNumber,
    InboundCall,
    InboundCallEvent,
    InboundCallStatus,
    InboundNumberStatus,
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
    "conversation_intake_confirmation_receipts": TableOwnership(
        module="conversations",
        agency_column="agency_id",
    ),
    "agency_receptionist_settings": TableOwnership(
        module="receptionist",
        agency_column="agency_id",
    ),
    "agency_approved_faqs": TableOwnership(
        module="approved_faqs",
        agency_column="agency_id",
    ),
    "agency_leads": TableOwnership(module="leads", agency_column="agency_id"),
    "lead_handoff_requests": TableOwnership(
        module="leads",
        agency_column="agency_id",
    ),
    "agency_call_policies": TableOwnership(
        module="telephony",
        agency_column="agency_id",
    ),
    "agency_inbound_numbers": TableOwnership(
        module="telephony",
        agency_column="agency_id",
    ),
    "inbound_calls": TableOwnership(
        module="telephony",
        agency_column="agency_id",
    ),
    "inbound_call_events": TableOwnership(
        module="telephony",
        agency_column="agency_id",
    ),
    "audit_events": TableOwnership(module="audit", agency_column="agency_id"),
    "idempotency_records": TableOwnership(
        module="idempotency",
        agency_column="agency_id",
    ),
}

__all__ = [
    "TABLE_OWNERSHIP",
    "Agency",
    "AgencyApprovedFaq",
    "AgencyCallPolicy",
    "AgencyInboundNumber",
    "AgencyLead",
    "AgencyMembership",
    "AgencyReceptionistSettings",
    "AppUser",
    "ApprovedFaqStatus",
    "AuditEvent",
    "Base",
    "ConversationChannel",
    "ConversationIntake",
    "ConversationIntakeConfirmationReceipt",
    "ConversationSession",
    "Customer",
    "HandoffContactMethod",
    "HandoffRequestKind",
    "HandoffStatus",
    "IdempotencyRecord",
    "InboundCall",
    "InboundCallEvent",
    "InboundCallStatus",
    "InboundNumberStatus",
    "LeadHandoffRequest",
    "LeadStatus",
    "LeadUrgency",
    "TableOwnership",
]
