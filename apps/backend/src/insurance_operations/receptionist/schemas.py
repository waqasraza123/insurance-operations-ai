from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


class ReceptionistSettingsContent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    public_name: str = Field(min_length=1, max_length=160)
    greeting: str = Field(min_length=1, max_length=600)
    office_hours: str = Field(min_length=1, max_length=1_000)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, min_length=7, max_length=32)
    supported_insurance_categories: list[str] = Field(min_length=1, max_length=20)
    escalation_message: str = Field(min_length=1, max_length=600)

    @field_validator("contact_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not any(character.isdigit() for character in normalized):
            raise ValueError("contact phone must contain a digit")
        if any(
            not (character.isdigit() or character in " +()-.")
            for character in normalized
        ):
            raise ValueError("contact phone contains unsupported characters")
        return normalized

    @field_validator("supported_insurance_categories")
    @classmethod
    def normalize_categories(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or len(normalized) > 80:
                raise ValueError(
                    "insurance categories must contain between 1 and 80 characters"
                )
            comparison_key = normalized.casefold()
            if comparison_key in seen:
                raise ValueError("insurance categories must be unique")
            seen.add(comparison_key)
            normalized_values.append(normalized)
        return normalized_values

    @model_validator(mode="after")
    def require_contact_method(self) -> Self:
        if self.contact_email is None and self.contact_phone is None:
            raise ValueError("contact email or phone is required")
        return self


class ReceptionistSettingsInput(ReceptionistSettingsContent):
    expected_row_version: int = Field(ge=0)


class ReceptionistSettingsResponse(ReceptionistSettingsContent):
    id: UUID
    agency_id: UUID
    row_version: int
    created_at: datetime
    updated_at: datetime
