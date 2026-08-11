import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from insurance_operations.application import create_app
from insurance_operations.database.models.conversation import (
    ConversationIntake,
    ConversationSession,
    ConversationSessionStatus,
)
from insurance_operations.database.models.customer import Customer
from insurance_operations.database.models.identity import (
    Agency,
    AgencyEnvironment,
    AgencyMembership,
    AppUser,
)
from insurance_operations.database.models.lead import AgencyLead, LeadHandoffRequest
from insurance_operations.settings import (
    ApiSettings,
    DatabaseSettings,
    RuntimeEnvironment,
)

type JsonValue = (
    bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
)
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True)
class DevelopmentTelephonyApi:
    application: FastAPI
    agency_id: UUID
    lead_id: UUID


@pytest.fixture
def development_telephony_api(
    migrated_database: Engine,
    database_settings: DatabaseSettings,
) -> Iterator[DevelopmentTelephonyApi]:
    now = datetime.now(UTC)
    agency = Agency(
        name="Synthetic Telephone Agency",
        slug=f"synthetic-telephone-{uuid4()}",
        environment_kind=AgencyEnvironment.DEVELOPMENT.value,
    )
    app_user = AppUser(
        auth_subject=uuid4(),
        display_name="Synthetic Telephone Operator",
    )
    with Session(migrated_database) as session, session.begin():
        session.add_all([agency, app_user])
        session.flush()
        session.add(AgencyMembership(agency_id=agency.id, app_user_id=app_user.id))
        conversation_session = ConversationSession(
            agency_id=agency.id,
            initiated_by=app_user.id,
            status=ConversationSessionStatus.CONFIRMED.value,
            provider_metadata={"adapter": "test", "adapter_version": "1"},
            disclosure_accepted_at=now,
            microphone_consent_at=now,
            synthetic_data_acknowledged_at=now,
            maximum_duration_seconds=180,
            authorization_expires_at=now + timedelta(minutes=3),
            confirmation_expires_at=now + timedelta(minutes=30),
            authorized_at=now,
            ended_at=now,
            confirmed_at=now,
        )
        customer = Customer(
            agency_id=agency.id,
            full_name="Synthetic Telephone Caller",
            normalized_name="synthetic telephone caller",
            email="telephone@example.com",
            normalized_email="telephone@example.com",
            phone="+15550100200",
            normalized_phone="+15550100200",
            country_code="US",
            search_text="synthetic telephone caller telephone@example.com",
            created_by=app_user.id,
        )
        session.add_all([conversation_session, customer])
        session.flush()
        intake = ConversationIntake(
            agency_id=agency.id,
            customer_id=customer.id,
            conversation_session_id=conversation_session.id,
            created_by=app_user.id,
            intake_intent="Synthetic telephone callback request.",
            confirmed_transcript=[
                {"speaker": "AGENT", "text": "How may I help?"},
                {"speaker": "USER", "text": "Please arrange a callback."},
            ],
            confirmed_at=now,
        )
        session.add(intake)
        session.flush()
        lead = AgencyLead(
            agency_id=agency.id,
            customer_id=customer.id,
            conversation_intake_id=intake.id,
            status="NEW",
            urgency="NORMAL",
            summary=intake.intake_intent,
            created_by=app_user.id,
            updated_by=app_user.id,
        )
        session.add(lead)
        session.flush()
        agency_id = agency.id
        app_user_id = app_user.id
        lead_id = lead.id

    settings = ApiSettings(
        app_environment=RuntimeEnvironment.DEVELOPMENT,
        api_host="127.0.0.1",
        api_port=8000,
        database_url=database_settings.runtime_database_url,
        database_ssl_mode=database_settings.database_ssl_mode,
        conversation_ai_enabled=False,
        development_actor_user_id=app_user_id,
    )
    yield DevelopmentTelephonyApi(
        application=create_app(settings, migrated_database),
        agency_id=agency_id,
        lead_id=lead_id,
    )


async def request_json(
    application: FastAPI,
    method: str,
    path: str,
    body: JsonObject | None = None,
) -> tuple[int, dict[str, object]]:
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, json=body)
    response_body = response.json()
    assert isinstance(response_body, dict)
    return response.status_code, response_body


def event_body(
    event_key: str,
    event_type: str,
    occurred_at: datetime,
) -> JsonObject:
    return {
        "event_key": event_key,
        "event_type": event_type,
        "occurred_at": occurred_at.isoformat(),
    }


def test_after_hours_transfer_falls_back_to_one_callback_handoff(
    development_telephony_api: DevelopmentTelephonyApi,
    migrated_database: Engine,
) -> None:
    monday_open = datetime(2026, 8, 10, 14, 0, tzinfo=UTC)
    sunday_closed = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    policy_status, policy = asyncio.run(
        request_json(
            development_telephony_api.application,
            "PUT",
            "/api/v1/development/call-policy",
            {
                "inbound_enabled": True,
                "timezone": "UTC",
                "availability_windows": [
                    {"weekday": 0, "start_local": "09:00", "end_local": "17:00"}
                ],
                "transfer_enabled": True,
                "transfer_destination_e164": "+15550100201",
                "transfer_ring_timeout_seconds": 20,
                "max_concurrent_calls": 2,
                "daily_call_limit": 10,
                "callback_fallback_enabled": True,
                "after_hours_message": "The team is currently outside office hours.",
                "unavailable_message": "The team is currently unavailable.",
                "expected_row_version": 0,
            },
        )
    )
    assert policy_status == 200
    assert policy["row_version"] == 1

    number_status, _number = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            "/api/v1/development/inbound-numbers",
            {
                "phone_number_e164": "+15550100202",
                "label": "Synthetic main line",
                "status": "ACTIVE",
            },
        )
    )
    assert number_status == 201

    receive_status, received = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            "/api/v1/development/inbound-calls",
            {
                "adapter_name": "synthetic_adapter",
                "adapter_version": "1",
                "source_call_reference": "synthetic-call-after-hours",
                "called_number_e164": "+15550100202",
                "caller_number_e164": "+15550100200",
                "occurred_at": sunday_closed.isoformat(),
            },
        )
    )
    assert receive_status == 201
    assert received["action"] == "ANSWER_AI"
    call = received["call"]
    assert isinstance(call, dict)
    call_id = call["id"]
    assert isinstance(call_id, str)

    answered_status, answered = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            f"/api/v1/development/inbound-calls/{call_id}/events",
            event_body("answered", "ANSWERED", sunday_closed),
        )
    )
    assert answered_status == 200
    assert answered["action"] == "CONTINUE_AI"

    transfer_status, fallback = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            f"/api/v1/development/inbound-calls/{call_id}/events",
            event_body("transfer-requested", "TRANSFER_REQUESTED", sunday_closed),
        )
    )
    assert transfer_status == 200
    assert fallback["action"] == "COLLECT_CALLBACK"
    fallback_call = fallback["call"]
    assert isinstance(fallback_call, dict)
    assert fallback_call["status"] == "CALLBACK_PENDING"
    assert fallback_call["row_version"] == 3

    replay_status, replay = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            f"/api/v1/development/inbound-calls/{call_id}/events",
            event_body("transfer-requested", "TRANSFER_REQUESTED", sunday_closed),
        )
    )
    assert replay_status == 200
    assert replay["replayed"] is True

    link_status, linked = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            f"/api/v1/development/inbound-calls/{call_id}/lead",
            {
                "lead_id": str(development_telephony_api.lead_id),
                "expected_row_version": 3,
            },
        )
    )
    assert link_status == 200
    assert linked["action"] == "CALLBACK_CONFIRMED"
    linked_call = linked["call"]
    assert isinstance(linked_call, dict)
    assert linked_call["status"] == "CALLBACK_REQUESTED"

    with Session(migrated_database) as session:
        handoffs = session.scalars(
            select(LeadHandoffRequest).where(
                LeadHandoffRequest.inbound_call_id == UUID(call_id)
            )
        ).all()
    assert len(handoffs) == 1
    assert handoffs[0].request_kind == "CALLBACK"
    assert handoffs[0].preferred_contact_method == "PHONE"

    second_receive_status, second_received = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            "/api/v1/development/inbound-calls",
            {
                "adapter_name": "synthetic_adapter",
                "adapter_version": "1",
                "source_call_reference": "synthetic-call-open-hours",
                "called_number_e164": "+15550100202",
                "caller_number_e164": "+15550100203",
                "occurred_at": monday_open.isoformat(),
            },
        )
    )
    assert second_receive_status == 201
    second_call = second_received["call"]
    assert isinstance(second_call, dict)
    second_call_id = second_call["id"]
    assert isinstance(second_call_id, str)
    asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            f"/api/v1/development/inbound-calls/{second_call_id}/events",
            event_body("answered", "ANSWERED", monday_open),
        )
    )
    transfer_status, transfer = asyncio.run(
        request_json(
            development_telephony_api.application,
            "POST",
            f"/api/v1/development/inbound-calls/{second_call_id}/events",
            event_body("transfer-requested", "TRANSFER_REQUESTED", monday_open),
        )
    )
    assert transfer_status == 200
    assert transfer["action"] == "TRANSFER"
    assert transfer["transfer_destination_e164"] == "+15550100201"
    assert transfer["transfer_ring_timeout_seconds"] == 20
