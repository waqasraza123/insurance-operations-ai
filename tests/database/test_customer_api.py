import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from insurance_operations.application import create_app
from insurance_operations.database.models.customer import Customer
from insurance_operations.database.models.identity import (
    Agency,
    AgencyEnvironment,
    AgencyMembership,
    AppUser,
    MembershipStatus,
)
from insurance_operations.database.models.operations import (
    AuditEvent,
    IdempotencyRecord,
)
from insurance_operations.identity import (
    AccessTokenVerificationError,
    VerifiedIdentity,
)
from insurance_operations.settings import ApiSettings, RuntimeEnvironment


class FixedAccessTokenVerifier:
    def __init__(self, subject: UUID) -> None:
        self._subject = subject

    def verify(self, access_token: str) -> VerifiedIdentity:
        if access_token != "valid-test-token":
            raise AccessTokenVerificationError("invalid token")
        return VerifiedIdentity(subject=self._subject)


@dataclass(frozen=True)
class AuthorizedApi:
    application: FastAPI
    agency_id: UUID
    app_user_id: UUID


@pytest.fixture
def authorized_api(
    migrated_database: Engine,
) -> Iterator[AuthorizedApi]:
    subject = uuid4()
    agency = Agency(
        name="Voice Intake Test Agency",
        slug=f"voice-intake-{uuid4()}",
        environment_kind=AgencyEnvironment.DEVELOPMENT.value,
    )
    app_user = AppUser(
        auth_subject=subject,
        display_name="Test Intake User",
        email_snapshot="intake@example.test",
    )
    with Session(migrated_database) as session, session.begin():
        session.add_all([agency, app_user])
        session.flush()
        agency_id = agency.id
        app_user_id = app_user.id
        session.add(
            AgencyMembership(
                agency_id=agency_id,
                app_user_id=app_user_id,
            )
        )

    settings = ApiSettings(
        app_environment=RuntimeEnvironment.TEST,
        api_host="127.0.0.1",
        api_port=8000,
        database_url="postgresql://unused:unused@localhost/development",
        test_database_url="postgresql://unused:unused@localhost/test",
        supabase_auth_issuer="https://example.supabase.co/auth/v1",
        supabase_auth_jwks_url=(
            "https://example.supabase.co/auth/v1/.well-known/jwks.json"
        ),
    )
    application = create_app(
        settings,
        migrated_database,
        FixedAccessTokenVerifier(subject),
    )
    yield AuthorizedApi(application, agency_id, app_user_id)

    with Session(migrated_database) as session, session.begin():
        customer_ids = select(Customer.id).where(Customer.agency_id == agency_id)
        session.execute(
            delete(AuditEvent).where(AuditEvent.agency_id == agency_id)
        )
        session.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.agency_id == agency_id
            )
        )
        session.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        session.execute(
            delete(AgencyMembership).where(
                AgencyMembership.agency_id == agency_id
            )
        )
        session.execute(delete(AppUser).where(AppUser.id == app_user_id))
        session.execute(delete(Agency).where(Agency.id == agency_id))


async def post_customer(
    authorized_api: AuthorizedApi,
    *,
    idempotency_key: str,
    full_name: str,
) -> tuple[int, dict[str, object], dict[str, str]]:
    transport = ASGITransport(app=authorized_api.application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/customers",
            headers={
                "Authorization": "Bearer valid-test-token",
                "Idempotency-Key": idempotency_key,
            },
            json={"full_name": full_name, "email": "person@example.test"},
        )
    body = response.json()
    assert isinstance(body, dict)
    return response.status_code, body, dict(response.headers)


async def get_current_actor(
    authorized_api: AuthorizedApi,
) -> tuple[int, dict[str, object]]:
    transport = ASGITransport(app=authorized_api.application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer valid-test-token"},
        )
    body = response.json()
    assert isinstance(body, dict)
    return response.status_code, body


def test_actor_context_uses_active_database_membership(
    authorized_api: AuthorizedApi,
) -> None:
    status_code, body = asyncio.run(get_current_actor(authorized_api))

    assert status_code == 200
    assert body["app_user_id"] == str(authorized_api.app_user_id)
    assert body["agency_id"] == str(authorized_api.agency_id)


def test_protected_route_rejects_inactive_membership(
    authorized_api: AuthorizedApi,
    migrated_database: Engine,
) -> None:
    with Session(migrated_database) as session, session.begin():
        membership = session.scalar(
            select(AgencyMembership).where(
                AgencyMembership.agency_id == authorized_api.agency_id
            )
        )
        assert membership is not None
        membership.status = MembershipStatus.INACTIVE.value

    status_code, body = asyncio.run(get_current_actor(authorized_api))

    assert status_code == 403
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "AGENCY_ACCESS_DENIED"


def test_customer_creation_is_owned_audited_and_idempotent(
    authorized_api: AuthorizedApi,
    migrated_database: Engine,
) -> None:
    first = asyncio.run(
        post_customer(
            authorized_api,
            idempotency_key="customer-create-1",
            full_name="  Sample   Customer  ",
        )
    )
    second = asyncio.run(
        post_customer(
            authorized_api,
            idempotency_key="customer-create-1",
            full_name="  Sample   Customer  ",
        )
    )

    assert first[0] == 201
    assert second[0] == 201
    assert second[1] == first[1]
    assert second[2]["idempotent-replayed"] == "true"
    with Session(migrated_database) as session:
        assert session.scalar(
            select(func.count()).select_from(Customer).where(
                Customer.agency_id == authorized_api.agency_id,
                Customer.created_by == authorized_api.app_user_id,
            )
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.agency_id == authorized_api.agency_id,
                AuditEvent.event_type == "CUSTOMER_CREATED",
            )
        ) == 1


def test_customer_idempotency_key_rejects_changed_request(
    authorized_api: AuthorizedApi,
) -> None:
    asyncio.run(
        post_customer(
            authorized_api,
            idempotency_key="customer-create-conflict",
            full_name="First Customer",
        )
    )

    status_code, body, _headers = asyncio.run(
        post_customer(
            authorized_api,
            idempotency_key="customer-create-conflict",
            full_name="Different Customer",
        )
    )

    assert status_code == 409
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "IDEMPOTENCY_KEY_REUSED"
