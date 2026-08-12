import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from insurance_operations.application import create_app
from insurance_operations.conversations.contracts import (
    ConnectionGrant,
    ProviderSessionMetadata,
)
from insurance_operations.database.models.identity import (
    Agency,
    AgencyEnvironment,
    AgencyMembership,
    AppUser,
)
from insurance_operations.database.models.operations import AuditEvent
from insurance_operations.database.models.receptionist import (
    AgencyReceptionistSettings,
)
from insurance_operations.settings import (
    ApiSettings,
    DatabaseSettings,
    RuntimeEnvironment,
)

type JsonValue = (
    bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
)
type JsonObject = dict[str, JsonValue]


class FakeConversationProvider:
    def authorize_session(self) -> ConnectionGrant:
        return ConnectionGrant(
            transport="webrtc",
            credential="faq-test-credential",
            metadata=ProviderSessionMetadata(
                adapter="test_adapter",
                adapter_version="1",
                external_session_reference=f"external-{uuid4()}",
            ),
        )

    def close(self) -> None:
        return None


@dataclass(frozen=True)
class DevelopmentFaqApi:
    application: FastAPI
    agency_id: UUID


@pytest.fixture
def development_faq_api(
    migrated_database: Engine,
    database_settings: DatabaseSettings,
) -> Iterator[DevelopmentFaqApi]:
    agency = Agency(
        name="Synthetic FAQ Agency",
        slug=f"synthetic-faq-{uuid4()}",
        environment_kind=AgencyEnvironment.DEVELOPMENT.value,
    )
    app_user = AppUser(auth_subject=uuid4(), display_name="Synthetic FAQ Owner")
    with Session(migrated_database) as session, session.begin():
        session.add_all([agency, app_user])
        session.flush()
        session.add(AgencyMembership(agency_id=agency.id, app_user_id=app_user.id))
        session.add(
            AgencyReceptionistSettings(
                agency_id=agency.id,
                public_name="Synthetic FAQ Agency",
                greeting="Welcome to the synthetic FAQ test.",
                office_hours="Weekdays, 9 AM to 5 PM",
                contact_email="faq@example.com",
                contact_phone=None,
                supported_insurance_categories=["Auto"],
                escalation_message="A licensed team member will follow up.",
                created_by=app_user.id,
                updated_by=app_user.id,
            )
        )
        agency_id = agency.id
        app_user_id = app_user.id

    settings = ApiSettings(
        app_environment=RuntimeEnvironment.DEVELOPMENT,
        api_host="127.0.0.1",
        api_port=8000,
        database_url=database_settings.runtime_database_url,
        database_ssl_mode=database_settings.database_ssl_mode,
        conversation_ai_enabled=True,
        development_actor_user_id=app_user_id,
        elevenlabs_api_key="test-secret",
        elevenlabs_agent_id="agent_test",
        elevenlabs_privacy_confirmed=True,
    )
    yield DevelopmentFaqApi(
        application=create_app(
            settings,
            migrated_database,
            FakeConversationProvider(),
        ),
        agency_id=agency_id,
    )


async def request_json(
    application: FastAPI,
    method: str,
    path: str,
    body: JsonObject | None = None,
) -> tuple[int, JsonValue]:
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, json=body)
    return response.status_code, response.json()


def test_approved_faq_lifecycle_and_safe_preview_lookup(
    development_faq_api: DevelopmentFaqApi,
) -> None:
    create_status, created_body = asyncio.run(
        request_json(
            development_faq_api.application,
            "POST",
            "/api/v1/development/approved-faqs",
            {
                "question": "What are your office hours?",
                "approved_answer": "We are open weekdays from 9 AM to 5 PM.",
            },
        )
    )
    assert create_status == 201
    assert isinstance(created_body, dict)
    assert created_body["status"] == "INACTIVE"
    faq_id = created_body["id"]
    assert isinstance(faq_id, str)

    unmatched_status, unmatched = asyncio.run(
        request_json(
            development_faq_api.application,
            "POST",
            "/api/v1/development/approved-faqs/lookup",
            {"query": "Please tell me your office hours"},
        )
    )
    assert unmatched_status == 200
    assert isinstance(unmatched, dict)
    assert unmatched["matched"] is False
    assert unmatched["answer"] is None

    activate_status, active = asyncio.run(
        request_json(
            development_faq_api.application,
            "POST",
            f"/api/v1/development/approved-faqs/{faq_id}/activate",
            {"expected_row_version": 1},
        )
    )
    assert activate_status == 200
    assert isinstance(active, dict)
    assert active["status"] == "ACTIVE"
    assert active["row_version"] == 2

    matched_status, matched = asyncio.run(
        request_json(
            development_faq_api.application,
            "POST",
            "/api/v1/development/approved-faqs/lookup",
            {"query": "Please tell me your office hours"},
        )
    )
    assert matched_status == 200
    assert isinstance(matched, dict)
    assert matched["matched"] is True
    source = matched["source"]
    assert isinstance(source, dict)
    assert source["faq_id"] == faq_id
    assert source["row_version"] == 2

    stale_status, stale = asyncio.run(
        request_json(
            development_faq_api.application,
            "PUT",
            f"/api/v1/development/approved-faqs/{faq_id}",
            {
                "question": "What are your office hours?",
                "approved_answer": "Changed answer",
                "expected_row_version": 1,
            },
        )
    )
    assert stale_status == 409
    assert isinstance(stale, dict)
    error = stale["error"]
    assert isinstance(error, dict)
    assert error["code"] == "APPROVED_FAQ_VERSION_CONFLICT"


def test_live_lookup_requires_active_session_and_audits_source_only(
    development_faq_api: DevelopmentFaqApi,
    migrated_database: Engine,
) -> None:
    _status, created = asyncio.run(
        request_json(
            development_faq_api.application,
            "POST",
            "/api/v1/development/approved-faqs",
            {
                "question": "Which insurance categories do you support?",
                "approved_answer": "We support synthetic auto inquiries.",
                "status": "ACTIVE",
            },
        )
    )
    assert isinstance(created, dict)

    authorization_status, authorization = asyncio.run(
        request_json(
            development_faq_api.application,
            "POST",
            "/api/v1/development/conversation-sessions",
            {
                "ai_disclosure_accepted": True,
                "microphone_consent_granted": True,
                "synthetic_data_acknowledged": True,
            },
        )
    )
    assert authorization_status == 201
    assert isinstance(authorization, dict)
    session_id = authorization["session_id"]
    assert isinstance(session_id, str)

    raw_query = "Please tell me which insurance categories you support"
    lookup_status, lookup = asyncio.run(
        request_json(
            development_faq_api.application,
            "POST",
            f"/api/v1/development/conversation-sessions/{session_id}/approved-faq-lookup",
            {"query": raw_query},
        )
    )
    assert lookup_status == 200
    assert isinstance(lookup, dict)
    assert lookup["matched"] is True

    with Session(migrated_database) as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.agency_id == development_faq_api.agency_id,
                AuditEvent.event_type == "AGENCY_APPROVED_FAQ_ANSWER_USED",
            )
        )

    assert event is not None
    assert event.details["conversation_session_id"] == session_id
    assert event.details["faq_id"] == created["id"]
    assert raw_query not in str(event.details)
