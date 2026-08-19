from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.customers import CustomerInput
from insurance_operations.database.models.conversation import (
    ConversationIntake,
    ConversationIntakeConfirmationReceipt,
    ConversationSession,
    ConversationSessionStatus,
)
from insurance_operations.database.models.identity import (
    Agency,
    AgencyEnvironment,
    AgencyMembership,
    AppUser,
)
from insurance_operations.database.models.lead import AgencyLead, LeadUrgency
from insurance_operations.database.models.telephony import (
    AgencyCallPolicy,
    AgencyInboundNumber,
    InboundCall,
    InboundNumberStatus,
)
from insurance_operations.telephony.contracts import (
    TransferInstruction,
    VerifiedInboundCall,
    VerifiedTransferResult,
)
from insurance_operations.telephony.demo import PhoneDemoService, PhoneDemoState
from insurance_operations.telephony.phone_schemas import (
    PhoneConsentInput,
    PhoneIntakeConfirmationInput,
)
from insurance_operations.telephony.phone_service import PhoneReceptionistService
from insurance_operations.telephony.schemas import InboundCallReceiveInput
from insurance_operations.telephony.service import TelephonyService

CALLED_NUMBER = "+15559991001"
CALLER_NUMBER = "+15559991002"


class NoopTelephonyAdapter:
    def verify_inbound_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> VerifiedInboundCall:
        del headers, body
        raise AssertionError("inbound webhook was not expected")

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


def test_confirmed_phone_call_materializes_one_intake_and_lead_after_post_call(
    migrated_database: Engine,
) -> None:
    now = datetime.now(UTC)
    agency = Agency(
        name="Synthetic Phone Agency",
        slug=f"synthetic-phone-{uuid4()}",
        environment_kind=AgencyEnvironment.DEVELOPMENT.value,
    )
    user = AppUser(
        auth_subject=uuid4(),
        display_name="Synthetic Phone Service User",
    )
    with Session(migrated_database) as session, session.begin():
        session.add_all([agency, user])
        session.flush()
        session.add(
            AgencyMembership(
                agency_id=agency.id,
                app_user_id=user.id,
            )
        )
        session.add(
            AgencyCallPolicy(
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
        )
        session.add(
            AgencyInboundNumber(
                agency_id=agency.id,
                phone_number_e164=CALLED_NUMBER,
                label="Synthetic phone line",
                status=InboundNumberStatus.ACTIVE.value,
                created_by=user.id,
                updated_by=user.id,
            )
        )
        agency_id = agency.id
        user_id = user.id

    factory = sessionmaker(
        bind=migrated_database,
        class_=Session,
        expire_on_commit=False,
    )
    telephony = TelephonyService(session_factory=factory)
    received = telephony.receive_provider_call(
        request=InboundCallReceiveInput(
            adapter_name="twilio",
            adapter_version="1",
            source_call_reference="CA" + ("e" * 32),
            called_number_e164=CALLED_NUMBER,
            caller_number_e164=CALLER_NUMBER,
            occurred_at=now,
        ),
        correlation_id=uuid4(),
    )
    phone = PhoneReceptionistService(
        session_factory=factory,
        telephony_service=telephony,
        telephony_adapter=NoopTelephonyAdapter(),
        development_actor_user_id=user_id,
        maximum_duration_seconds=180,
        confirmation_window_minutes=30,
    )
    conversation_id = f"conv_{uuid4()}"
    consent = phone.accept_consent(
        request=PhoneConsentInput(
            inbound_call_id=received.call.id,
            conversation_id=conversation_id,
            ai_disclosure_accepted=True,
            microphone_consent_granted=True,
            synthetic_data_acknowledged=True,
        ),
        correlation_id=uuid4(),
    )
    confirmation_request = PhoneIntakeConfirmationInput(
        inbound_call_id=received.call.id,
        conversation_id=conversation_id,
        customer=CustomerInput(
            full_name="Synthetic Phone Caller",
            phone=CALLER_NUMBER,
        ),
        intake_intent="Request a synthetic auto-policy callback.",
        urgency=LeadUrgency.NORMAL,
        explicit_verbal_confirmation=True,
    )
    phone.confirm_intake(
        request=confirmation_request,
        correlation_id=uuid4(),
    )
    confirmation_replay = phone.confirm_intake(
        request=confirmation_request,
        correlation_id=uuid4(),
    )

    assert confirmation_replay.replayed is True

    with Session(migrated_database) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ConversationIntake)
                .where(ConversationIntake.agency_id == agency_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AgencyLead)
                .where(AgencyLead.agency_id == agency_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ConversationIntakeConfirmationReceipt)
                .where(ConversationIntakeConfirmationReceipt.agency_id == agency_id)
            )
            == 1
        )

    payload: dict[str, object] = {
        "type": "post_call_transcription",
        "event_timestamp": int((now + timedelta(seconds=30)).timestamp()),
        "data": {
            "conversation_id": conversation_id,
            "conversation_initiation_client_data": {
                "dynamic_variables": {
                    "phone_inbound_call_id": str(received.call.id),
                }
            },
            "transcript": [
                {"role": "agent", "message": "Do you confirm this intake?"},
                {"role": "user", "message": "Yes, I confirm."},
            ],
        },
    }
    phone.finalize_post_call(payload=payload, correlation_id=uuid4())
    phone.finalize_post_call(payload=payload, correlation_id=uuid4())

    with Session(migrated_database) as session:
        conversation_session = session.get(
            ConversationSession,
            consent.conversation_session_id,
        )
        inbound_call = session.get(InboundCall, received.call.id)
        intake = session.scalar(
            select(ConversationIntake).where(
                ConversationIntake.conversation_session_id
                == consent.conversation_session_id
            )
        )
        lead_count = session.scalar(
            select(func.count())
            .select_from(AgencyLead)
            .where(AgencyLead.agency_id == agency_id)
        )

    assert conversation_session is not None
    assert conversation_session.status == ConversationSessionStatus.CONFIRMED.value
    assert inbound_call is not None
    assert inbound_call.lead_id is not None
    assert intake is not None
    assert intake.confirmed_transcript[-1]["text"] == "Yes, I confirm."
    assert lead_count == 1

    demo_service = PhoneDemoService(
        session_factory=factory,
        result_ttl_minutes=15,
        clock=lambda: now + timedelta(seconds=35),
    )
    demo_status = demo_service.latest_status(agency_id=agency_id)

    assert demo_status.state is PhoneDemoState.LEAD_CREATED
    assert demo_status.consent_completed is True
    assert demo_status.lead_created is True
    assert demo_status.urgency is LeadUrgency.NORMAL
    assert set(demo_status.model_dump()) == {
        "state",
        "received_at",
        "answered_at",
        "ended_at",
        "consent_completed",
        "lead_created",
        "urgency",
        "handoff_kind",
        "handoff_status",
    }

    stale_status = PhoneDemoService(
        session_factory=factory,
        result_ttl_minutes=15,
        clock=lambda: now + timedelta(minutes=16),
    ).latest_status(agency_id=agency_id)

    assert stale_status.state is PhoneDemoState.READY
