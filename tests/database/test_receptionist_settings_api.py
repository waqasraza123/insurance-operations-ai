import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from insurance_operations.application import create_app
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


@dataclass(frozen=True)
class DevelopmentReceptionistApi:
    application: FastAPI
    agency_id: UUID
    app_user_id: UUID


@pytest.fixture
def development_receptionist_api(
    migrated_database: Engine,
    database_settings: DatabaseSettings,
) -> Iterator[DevelopmentReceptionistApi]:
    agency = Agency(
        name="Synthetic Receptionist Agency",
        slug=f"synthetic-receptionist-{uuid4()}",
        environment_kind=AgencyEnvironment.DEVELOPMENT.value,
    )
    app_user = AppUser(
        auth_subject=uuid4(),
        display_name="Synthetic Receptionist Administrator",
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
        conversation_ai_enabled=False,
        development_actor_user_id=app_user_id,
    )
    yield DevelopmentReceptionistApi(
        application=create_app(settings, migrated_database),
        agency_id=agency_id,
        app_user_id=app_user_id,
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


def valid_settings(*, expected_row_version: int) -> JsonObject:
    return {
        "public_name": "Harborline Insurance",
        "greeting": "Welcome to our synthetic AI receptionist.",
        "office_hours": "Monday through Friday, 9 AM to 5 PM Eastern",
        "contact_email": "receptionist@example.com",
        "contact_phone": None,
        "supported_insurance_categories": ["Auto", "Homeowners"],
        "escalation_message": "A licensed team member will follow up.",
        "expected_row_version": expected_row_version,
    }


def test_settings_create_read_update_are_owned_audited_and_versioned(
    development_receptionist_api: DevelopmentReceptionistApi,
    migrated_database: Engine,
) -> None:
    missing_status, missing_body = asyncio.run(
        request_json(
            development_receptionist_api.application,
            "GET",
            "/api/v1/development/receptionist-settings",
        )
    )
    assert missing_status == 404
    missing_error = missing_body["error"]
    assert isinstance(missing_error, dict)
    assert missing_error["code"] == "RECEPTIONIST_SETTINGS_NOT_FOUND"

    create_status, created = asyncio.run(
        request_json(
            development_receptionist_api.application,
            "PUT",
            "/api/v1/development/receptionist-settings",
            valid_settings(expected_row_version=0),
        )
    )
    assert create_status == 200
    assert created["agency_id"] == str(development_receptionist_api.agency_id)
    assert created["row_version"] == 1

    get_status, fetched = asyncio.run(
        request_json(
            development_receptionist_api.application,
            "GET",
            "/api/v1/development/receptionist-settings",
        )
    )
    assert get_status == 200
    assert fetched == created

    update_body = valid_settings(expected_row_version=1)
    update_body["office_hours"] = "Weekdays, 8 AM to 6 PM Eastern"
    update_status, updated = asyncio.run(
        request_json(
            development_receptionist_api.application,
            "PUT",
            "/api/v1/development/receptionist-settings",
            update_body,
        )
    )
    assert update_status == 200
    assert updated["row_version"] == 2

    stale_status, stale_body = asyncio.run(
        request_json(
            development_receptionist_api.application,
            "PUT",
            "/api/v1/development/receptionist-settings",
            valid_settings(expected_row_version=1),
        )
    )
    assert stale_status == 409
    stale_error = stale_body["error"]
    assert isinstance(stale_error, dict)
    assert stale_error["code"] == "RECEPTIONIST_SETTINGS_VERSION_CONFLICT"

    with Session(migrated_database) as session:
        settings_count = session.scalar(
            select(func.count())
            .select_from(AgencyReceptionistSettings)
            .where(
                AgencyReceptionistSettings.agency_id
                == development_receptionist_api.agency_id
            )
        )
        audit_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.agency_id == development_receptionist_api.agency_id
            )
        ).all()

    assert settings_count == 1
    assert [event.event_type for event in audit_events] == [
        "AGENCY_RECEPTIONIST_SETTINGS_CREATED",
        "AGENCY_RECEPTIONIST_SETTINGS_UPDATED",
    ]
    assert audit_events[1].details["changed_fields"] == ["office_hours"]
    assert all("Welcome" not in str(event.details) for event in audit_events)


def test_settings_validation_requires_contact_and_unique_categories(
    development_receptionist_api: DevelopmentReceptionistApi,
) -> None:
    request = valid_settings(expected_row_version=0)
    request["contact_email"] = None
    request["contact_phone"] = None
    request["supported_insurance_categories"] = ["Auto", "auto"]

    status_code, body = asyncio.run(
        request_json(
            development_receptionist_api.application,
            "PUT",
            "/api/v1/development/receptionist-settings",
            request,
        )
    )

    assert status_code == 422
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "VALIDATION_FAILED"
