import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from insurance_operations.database.models.customer import Customer
from insurance_operations.database.models.operations import (
    AuditActorType,
    AuditEvent,
    IdempotencyRecord,
    IdempotencyStatus,
)
from insurance_operations.errors import ApiError
from insurance_operations.identity import ActorContext

CREATE_CUSTOMER_ROUTE_KEY = "POST /api/v1/customers"


class CustomerAddressInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    state_code: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str = Field(default="US", min_length=2, max_length=2)

    @field_validator("state_code", "country_code")
    @classmethod
    def uppercase_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.upper()
        if not re.fullmatch(r"[A-Z]{2}", normalized_value):
            raise ValueError("code must contain two ASCII letters")
        return normalized_value


class CustomerCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=40)
    address: CustomerAddressInput | None = None
    duplicate_override: bool = False
    acknowledged_duplicate_customer_ids: list[UUID] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized_value = normalize_display_text(value)
        if not normalized_value or len(normalized_value) > 200:
            raise ValueError("full_name must contain between 1 and 200 characters")
        return normalized_value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"\+?[0-9().\- xX]+", value):
            raise ValueError("phone contains unsupported characters")
        digit_count = sum(character.isdigit() for character in value)
        if not 7 <= digit_count <= 15:
            raise ValueError("phone must contain between 7 and 15 digits")
        return value

    @model_validator(mode="after")
    def reject_unavailable_duplicate_override(self) -> Self:
        if self.duplicate_override or self.acknowledged_duplicate_customer_ids:
            raise ValueError("duplicate override is not available in this slice")
        return self


class CustomerView(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    address: CustomerAddressInput
    created_at: datetime
    updated_at: datetime
    row_version: int


class CustomerCreateResponse(BaseModel):
    customer: CustomerView
    warnings: list[dict[str, Any]]
    next_actions: list[dict[str, Any]]


def create_customer(
    session: Session,
    *,
    actor: ActorContext,
    request: CustomerCreateInput,
    idempotency_key: str,
    correlation_id: UUID,
    retention_hours: int,
) -> tuple[CustomerCreateResponse, bool]:
    now = datetime.now(UTC)
    fingerprint = request_fingerprint(request)
    insert_statement = (
        insert(IdempotencyRecord)
        .values(
            agency_id=actor.agency_id,
            actor_scope_type="APP_USER",
            actor_scope_id=actor.app_user_id,
            route_key=CREATE_CUSTOMER_ROUTE_KEY,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            status=IdempotencyStatus.IN_PROGRESS.value,
            expires_at=now + timedelta(hours=retention_hours),
        )
        .on_conflict_do_nothing(
            constraint="uq_idempotency_records_scope",
        )
        .returning(IdempotencyRecord.id)
    )

    with session.begin():
        record_id = session.scalar(insert_statement)
        if record_id is None:
            existing_record = session.scalar(
                select(IdempotencyRecord)
                .where(
                    IdempotencyRecord.actor_scope_type == "APP_USER",
                    IdempotencyRecord.actor_scope_id == actor.app_user_id,
                    IdempotencyRecord.route_key == CREATE_CUSTOMER_ROUTE_KEY,
                    IdempotencyRecord.idempotency_key == idempotency_key,
                )
                .with_for_update()
            )
            return replay_customer_creation(existing_record, fingerprint), True

        customer = customer_from_request(request, actor)
        session.add(customer)
        session.flush()

        response = response_from_customer(customer)
        session.add(
            AuditEvent(
                agency_id=actor.agency_id,
                actor_type=AuditActorType.STAFF.value,
                actor_user_id=actor.app_user_id,
                event_type="CUSTOMER_CREATED",
                occurred_at=now,
                customer_id=customer.id,
                summary="Customer created",
                details={"captured_fields": captured_fields(request)},
                correlation_id=correlation_id,
                event_version=1,
            )
        )
        record = session.get(IdempotencyRecord, record_id)
        if record is None:
            raise RuntimeError("idempotency record was not persisted")
        record.status = IdempotencyStatus.COMPLETED.value
        record.response_status = 201
        record.response_body = response.model_dump(mode="json")
        record.resource_type = "CUSTOMER"
        record.resource_id = customer.id
        record.completed_at = now

    return response, False


def replay_customer_creation(
    record: IdempotencyRecord | None,
    fingerprint: str,
) -> CustomerCreateResponse:
    if record is None:
        raise ApiError(
            status_code=409,
            code="IDEMPOTENCY_CONFLICT",
            message="The idempotency request could not be resolved",
        )
    if record.request_fingerprint != fingerprint:
        raise ApiError(
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            message="The idempotency key was already used for another request",
        )
    if (
        record.status != IdempotencyStatus.COMPLETED.value
        or record.response_body is None
    ):
        raise ApiError(
            status_code=409,
            code="IDEMPOTENCY_IN_PROGRESS",
            message="A request with this idempotency key is still in progress",
        )
    return CustomerCreateResponse.model_validate(record.response_body)


def customer_from_request(
    request: CustomerCreateInput,
    actor: ActorContext,
) -> Customer:
    address = request.address or CustomerAddressInput()
    full_name = normalize_display_text(request.full_name)
    email = str(request.email) if request.email is not None else None
    phone = request.phone
    normalized_email = email.casefold() if email is not None else None
    normalized_phone = normalize_phone(phone)
    search_parts = [
        full_name.casefold(),
        normalized_email,
        normalized_phone,
        address.line1,
        address.line2,
        address.city,
        address.state_code,
        address.postal_code,
    ]
    return Customer(
        agency_id=actor.agency_id,
        full_name=full_name,
        normalized_name=full_name.casefold(),
        email=email,
        normalized_email=normalized_email,
        phone=phone,
        normalized_phone=normalized_phone,
        address_line1=address.line1,
        address_line2=address.line2,
        city=address.city,
        state_code=address.state_code,
        postal_code=address.postal_code,
        country_code=address.country_code,
        search_text=" ".join(part.casefold() for part in search_parts if part),
        created_by=actor.app_user_id,
    )


def response_from_customer(customer: Customer) -> CustomerCreateResponse:
    return CustomerCreateResponse(
        customer=CustomerView(
            id=customer.id,
            full_name=customer.full_name,
            email=customer.email,
            phone=customer.phone,
            address=CustomerAddressInput(
                line1=customer.address_line1,
                line2=customer.address_line2,
                city=customer.city,
                state_code=customer.state_code,
                postal_code=customer.postal_code,
                country_code=customer.country_code,
            ),
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            row_version=customer.row_version,
        ),
        warnings=[],
        next_actions=[],
    )


def request_fingerprint(request: CustomerCreateInput) -> str:
    canonical_request = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_request.encode()).hexdigest()


def normalize_display_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return f"+{digits}" if value.lstrip().startswith("+") else digits


def captured_fields(request: CustomerCreateInput) -> list[str]:
    fields = ["full_name"]
    if request.email is not None:
        fields.append("email")
    if request.phone is not None:
        fields.append("phone")
    if request.address is not None:
        fields.append("address")
    return fields
