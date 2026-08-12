from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ApprovedFaqStatusValue = Literal["ACTIVE", "INACTIVE"]


class ApprovedFaqContent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=300)
    approved_answer: str = Field(min_length=1, max_length=2_000)


class ApprovedFaqCreateInput(ApprovedFaqContent):
    status: ApprovedFaqStatusValue = "INACTIVE"


class ApprovedFaqUpdateInput(ApprovedFaqContent):
    expected_row_version: int = Field(ge=1)


class ApprovedFaqStatusInput(BaseModel):
    expected_row_version: int = Field(ge=1)


class ApprovedFaqResponse(ApprovedFaqContent):
    id: UUID
    agency_id: UUID
    status: ApprovedFaqStatusValue
    row_version: int
    created_at: datetime
    updated_at: datetime


class ApprovedFaqLookupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)


class ApprovedFaqSource(BaseModel):
    faq_id: UUID
    question: str
    row_version: int


class ApprovedFaqLookupResponse(BaseModel):
    matched: bool
    answer: str | None
    fallback_message: str
    source: ApprovedFaqSource | None
