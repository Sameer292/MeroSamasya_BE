from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enum import IssueStatusEnum


class IssueModerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str | None = Field(default=None, min_length=1)
    status: IssueStatusEnum | None = None

    @model_validator(mode="after")
    def require_change_fields(self):
        values = self.model_dump(exclude_unset=True)
        if not values or any(value is None for value in values.values()):
            raise ValueError("Supply a category_id, a status, or both, with non-null values")
        return self


class ModerationChange(BaseModel):
    field: Literal["category_id", "status", "resolved_at"]
    previous: str | None
    current: str | None


class ModerationEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reviewer_id: str
    created_at: datetime
    changes: list[ModerationChange]


class ModeratedIssue(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category_id: str | None
    status: IssueStatusEnum
    resolved_at: datetime | None
    updated_at: datetime | None


class IssueModerationResult(BaseModel):
    issue: ModeratedIssue
    event: ModerationEvent | None


class IssueModerationResponse(BaseModel):
    data: IssueModerationResult


class ModerationHistoryResponse(BaseModel):
    data: list[ModerationEvent]
