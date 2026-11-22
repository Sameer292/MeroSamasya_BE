from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enum import AccountStatusEnum
from app.schemas.schema import IssueData, LocationSchema, PaginationMeta


class SubscriberPagination(BaseModel):
    page: int = Field(default=1, ge=1, le=2_147_483_647)
    limit: int = Field(default=10, ge=1, le=100)


class SubscriberDirectoryQuery(SubscriberPagination):
    search: str | None = Field(default=None, max_length=200)
    account_status: AccountStatusEnum | None = None


class SubscriberProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str | None
    email: str
    phone: str | None
    location: LocationSchema | None
    profile_picture_url: str | None
    account_status: AccountStatusEnum
    created_at: datetime | None
    updated_at: datetime | None
    deleted_at: datetime | None
    kyc_status: str | None = None


class SubscriberData(SubscriberProfile):
    reported_count: int
    resolved_count: int


class SubscriberHistoryIssue(IssueData):
    upvote_count: int | None = None
    created_at: datetime | None
    updated_at: datetime | None


class SubscriberIssueHistory(BaseModel):
    meta: PaginationMeta
    issues: list[SubscriberHistoryIssue]


class SubscriberDetail(SubscriberData):
    issue_history: SubscriberIssueHistory


class SubscriberDirectoryPage(BaseModel):
    meta: PaginationMeta
    subscribers: list[SubscriberData]


class SubscriberDirectoryResponse(BaseModel):
    data: SubscriberDirectoryPage


class SubscriberDetailResponse(BaseModel):
    data: SubscriberDetail
