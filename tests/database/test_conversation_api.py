import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from insurance_operations.application import create_app
from insurance_operations.conversations.contracts import (
    ConnectionGrant,
    ProviderSessionMetadata,
)
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
from insurance_operations.database.models.operations import AuditEvent
from insurance_operations.settings import (
    ApiSettings,
    DatabaseSettings,
    RuntimeEnvironment,
)

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]


class FakeConversationProvider:
    def authorize_session(self) -> ConnectionGrant:
        return ConnectionGrant(
            transport="webrtc",
            credential="short-lived-test-credential",
            metadata=ProviderSessionMetadata(
                adapter="test_adapter",
                adapter_version="1",
                external_session_reference=f"external-{uuid4()}",
            ),
        )

    def close(self) -> None:
        return None


@dataclass(frozen=True)
class DevelopmentConversationApi:
    application: FastAPI
    agency_id: UUID
    app_user_id: UUID


@pytest.fixture
def development_conversation_api(
    migrated_database: Engine,
    database_settings: DatabaseSettings,
) -> Iterator[DevelopmentConversationApi]:
    agency = Agency(
        name="Synthetic Voice Test Agency",
        slug=f"synthetic-voice-{uuid4()}",
        environment_kind=AgencyEnvironment.DEVELOPMENT.value,
    )
    app_user = AppUser(
        auth_subject=uuid4(),
        display_name="Synthetic Voice Tester",
    )
    with Session(migrated_database) as session, session.begin():
        session.add_all([agency, app_user])
        session.flush()
        session.add(
            AgencyMembership(
                agency_id=agency.id,
                app_user_id=app_user.id,
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
    yield DevelopmentConversationApi(
        create_app(settings, migrated_database, FakeConversationProvider()),
        agency_id,
        app_user_id,
    )


async def post_json(
    application: FastAPI,
    path: str,
    body: JsonObject,
    *,
    idempotency_key: str | None = None,
) -> tuple[int, dict[str, object], dict[str, str]]:
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, headers=headers, json=body)
    response_body = response.json()
    assert isinstance(response_body, dict)
    return response.status_code, response_body, dict(response.headers)


def authorize_session(
    api: DevelopmentConversationApi,
) -> tuple[int, dict[str, object], dict[str, str]]:
    return asyncio.run(
        post_json(
            api.application,
            "/api/v1/development/conversation-sessions",
            {
                "ai_disclosure_accepted": True,
                "microphone_consent_granted": True,
                "synthetic_data_acknowledged": True,
            },
        )
    )


def test_session_authorization_requires_all_acknowledgements(
    development_conversation_api: DevelopmentConversationApi,
) -> None:
    status_code, body, _headers = asyncio.run(
        post_json(
            development_conversation_api.application,
            "/api/v1/development/conversation-sessions",
            {
                "ai_disclosure_accepted": True,
                "microphone_consent_granted": True,
                "synthetic_data_acknowledged": False,
            },
        )
    )

    assert status_code == 422
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "SYNTHETIC_DATA_ACKNOWLEDGEMENT_REQUIRED"


def test_confirmed_intake_is_owned_audited_transactional_and_idempotent(
    development_conversation_api: DevelopmentConversationApi,
    migrated_database: Engine,
) -> None:
    status_code, authorization, _headers = authorize_session(
        development_conversation_api
    )
    assert status_code == 201
    session_id = authorization["session_id"]
    assert isinstance(session_id, str)
    connection = authorization["connection"]
    assert isinstance(connection, dict)
    assert connection["credential"] == "short-lived-test-credential"

    end_status, _end_body, _headers = asyncio.run(
        post_json(
            development_conversation_api.application,
            f"/api/v1/development/conversation-sessions/{session_id}/end",
            {"outcome": "COMPLETED"},
        )
    )
    assert end_status == 200

    confirmation: JsonObject = {
        "conversation_session_id": session_id,
        "customer": {
            "full_name": "Synthetic Sample Customer",
            "email": "synthetic@example.test",
        },
        "intake_intent": "Explore a synthetic renters insurance scenario.",
        "transcript": [
            {"speaker": "AGENT", "text": "How may I help with insurance?"},
            {"speaker": "USER", "text": "I want to discuss renters coverage."},
        ],
    }
    first = asyncio.run(
        post_json(
            development_conversation_api.application,
            "/api/v1/development/conversation-intakes",
            confirmation,
            idempotency_key="confirm-synthetic-intake",
        )
    )
    second = asyncio.run(
        post_json(
            development_conversation_api.application,
            "/api/v1/development/conversation-intakes",
            confirmation,
            idempotency_key="confirm-synthetic-intake",
        )
    )

    assert first[0] == 201
    assert second[0] == 201
    assert second[1] == first[1]
    assert second[2]["idempotent-replayed"] == "true"
    with Session(migrated_database) as session:
        customer_count = session.scalar(
            select(func.count()).select_from(Customer).where(
                Customer.agency_id == development_conversation_api.agency_id
            )
        )
        intake_count = session.scalar(
            select(func.count()).select_from(ConversationIntake).where(
                ConversationIntake.agency_id
                == development_conversation_api.agency_id
            )
        )
        audit_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.agency_id == development_conversation_api.agency_id
            )
        ).all()
        conversation_session = session.get(ConversationSession, UUID(session_id))

    assert customer_count == 1
    assert intake_count == 1
    assert len(audit_events) == 2
    assert conversation_session is not None
    assert conversation_session.status == ConversationSessionStatus.CONFIRMED.value
    assert all(
        "synthetic@example.test" not in str(event.details)
        for event in audit_events
    )

    with pytest.raises(DBAPIError), migrated_database.begin() as connection:
        connection.execute(
            update(ConversationIntake)
            .where(
                ConversationIntake.agency_id
                == development_conversation_api.agency_id
            )
            .values(intake_intent="Mutated intent")
        )


def test_active_session_concurrency_is_limited_to_one(
    development_conversation_api: DevelopmentConversationApi,
) -> None:
    first_status, _body, _headers = authorize_session(development_conversation_api)
    second_status, second_body, _headers = authorize_session(
        development_conversation_api
    )

    assert first_status == 201
    assert second_status == 409
    error = second_body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "CONVERSATION_ALREADY_ACTIVE"


def test_session_over_duration_limit_cannot_enter_review(
    development_conversation_api: DevelopmentConversationApi,
    migrated_database: Engine,
) -> None:
    status_code, body, _headers = authorize_session(development_conversation_api)
    assert status_code == 201
    session_id = body["session_id"]
    assert isinstance(session_id, str)
    with migrated_database.begin() as connection:
        connection.execute(
            update(ConversationSession)
            .where(ConversationSession.id == UUID(session_id))
            .values(authorized_at=datetime.now(UTC) - timedelta(seconds=181))
        )

    end_status, end_body, _headers = asyncio.run(
        post_json(
            development_conversation_api.application,
            f"/api/v1/development/conversation-sessions/{session_id}/end",
            {"outcome": "COMPLETED"},
        )
    )

    assert end_status == 200
    assert end_body["status"] == "EXPIRED"
    assert end_body["review_available"] is False


def test_session_authorizations_are_limited_to_ten_per_utc_day(
    development_conversation_api: DevelopmentConversationApi,
) -> None:
    for _index in range(10):
        status_code, body, _headers = authorize_session(
            development_conversation_api
        )
        assert status_code == 201
        session_id = body["session_id"]
        assert isinstance(session_id, str)
        end_status, _end_body, _headers = asyncio.run(
            post_json(
                development_conversation_api.application,
                f"/api/v1/development/conversation-sessions/{session_id}/end",
                {"outcome": "INTERRUPTED"},
            )
        )
        assert end_status == 200

    status_code, body, _headers = authorize_session(development_conversation_api)

    assert status_code == 429
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "CONVERSATION_DAILY_LIMIT_REACHED"
