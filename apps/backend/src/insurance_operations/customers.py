import re
import unicodedata
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from insurance_operations.actors import ActorContext
from insurance_operations.database.models.customer import Customer


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


class CustomerInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=40)
    address: CustomerAddressInput | None = None

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


class CustomerView(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    address: CustomerAddressInput


def customer_from_input(request: CustomerInput, actor: ActorContext) -> Customer:
    address = request.address or CustomerAddressInput()
    email = str(request.email) if request.email is not None else None
    normalized_email = email.casefold() if email is not None else None
    normalized_phone = normalize_phone(request.phone)
    search_parts = [
        request.full_name.casefold(),
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
        full_name=request.full_name,
        normalized_name=request.full_name.casefold(),
        email=email,
        normalized_email=normalized_email,
        phone=request.phone,
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


def customer_view(customer: Customer) -> CustomerView:
    return CustomerView(
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
    )


def normalize_display_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return f"+{digits}" if value.lstrip().startswith("+") else digits
