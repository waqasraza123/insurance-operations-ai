from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.database.models.identity import (
    Agency,
    AgencyEnvironment,
    AppUser,
)
from insurance_operations.database.models.operations import (
    AuditActorType,
    AuditEvent,
)
from insurance_operations.database.models.telephony import (
    AgencyCallPolicy,
    AgencyInboundNumber,
    InboundCall,
    InboundCallEvent,
    InboundNumberStatus,
)
from insurance_operations.telephony.contracts import (
    TransferInstruction,
    VerifiedInboundCall,
    VerifiedTransferResult,
)
from insurance_operations.telephony.ingress import TelephonyIngressService
from insurance_operations.telephony.service import TelephonyService

CALL_REFERENCE = "CA" + ("b" * 32)
CALLED_NUMBER = "+15559990001"
CALLER_NUMBER = "+15559990002"


class FakeVerifiedAdapter:
    def __init__(
        self,
        calls: list[VerifiedInboundCall],
    ) -> None:
        self._calls = iter(calls)

    def verify_inbound_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> VerifiedInboundCall:
        del headers, body
        return next(self._calls)

    def request_transfer(
        self,
        *,
        source_call_reference: str,
        instruction: TransferInstruction,
    ) -> None:
        del source_call_reference, instruction

    def verify_transfer_callback(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> VerifiedTransferResult:
        del headers, body
        raise AssertionError("transfer callback was not expected")

    def close(self) -> None:
        return None


def test_verified_provider_call_routes_without_staff_actor_and_replays(
    migrated_database: Engine,
) -> None:
    agency = Agency(
        name="Synthetic Provider Agency",
        slug=f"synthetic-provider-{uuid4()}",
        environment_kind=AgencyEnvironment.DEVELOPMENT.value,
    )
    user = AppUser(
        auth_subject=uuid4(),
        display_name="Synthetic Provider Setup User",
    )

    with Session(migrated_database) as session, session.begin():
        session.add_all([agency, user])
        session.flush()

        policy = AgencyCallPolicy(
            agency_id=agency.id,
            inbound_enabled=True,
            timezone="UTC",
            availability_windows=[],
            transfer_enabled=False,
            transfer_destination_e164=None,
            transfer_ring_timeout_seconds=20,
            max_concurrent_calls=2,
            daily_call_limit=10,
            callback_fallback_enabled=True,
            after_hours_message="The team is outside office hours.",
            unavailable_message="The team is unavailable.",
            created_by=user.id,
            updated_by=user.id,
        )

        number = AgencyInboundNumber(
            agency_id=agency.id,
            phone_number_e164=CALLED_NUMBER,
            label="Synthetic provider line",
            status=InboundNumberStatus.ACTIVE.value,
            created_by=user.id,
            updated_by=user.id,
        )

        session.add_all([policy, number])
        session.flush()

        agency_id = agency.id

    first_time = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    retry_time = first_time + timedelta(seconds=2)

    calls = [
        VerifiedInboundCall(
            adapter_name="twilio",
            adapter_version="1",
            source_call_reference=CALL_REFERENCE,
            called_number_e164=CALLED_NUMBER,
            caller_number_e164=CALLER_NUMBER,
            occurred_at=first_time,
        ),
        VerifiedInboundCall(
            adapter_name="twilio",
            adapter_version="1",
            source_call_reference=CALL_REFERENCE,
            called_number_e164=CALLED_NUMBER,
            caller_number_e164=CALLER_NUMBER,
            occurred_at=retry_time,
        ),
    ]

    factory = sessionmaker(
        bind=migrated_database,
        class_=Session,
        expire_on_commit=False,
    )

    ingress = TelephonyIngressService(
        adapter=FakeVerifiedAdapter(calls),
        telephony_service=TelephonyService(
            session_factory=factory,
        ),
    )

    first = ingress.receive(
        headers={},
        body=b"",
        correlation_id=uuid4(),
    )

    replay = ingress.receive(
        headers={},
        body=b"",
        correlation_id=uuid4(),
    )

    assert first.action.value == "ANSWER_AI"
    assert first.replayed is False
    assert first.call.agency_id == agency_id

    assert replay.action.value == "ANSWER_AI"
    assert replay.replayed is True
    assert replay.call.id == first.call.id

    with Session(migrated_database) as session:
        call_count = session.scalar(
            select(func.count())
            .select_from(InboundCall)
            .where(
                InboundCall.adapter_name == "twilio",
                InboundCall.source_call_reference == CALL_REFERENCE,
            )
        )

        event_count = session.scalar(
            select(func.count())
            .select_from(InboundCallEvent)
            .where(
                InboundCallEvent.inbound_call_id == first.call.id,
                InboundCallEvent.event_type == "CALL_RECEIVED",
            )
        )

        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.agency_id == agency_id,
                AuditEvent.event_type == "INBOUND_CALL_RECEIVED",
            )
        )

    assert call_count == 1
    assert event_count == 1
    assert audit is not None
    assert audit.actor_type == AuditActorType.SYSTEM.value
    assert audit.actor_user_id is None
