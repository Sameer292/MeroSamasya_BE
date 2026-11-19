from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enum import IssueStatusEnum
from app.schemas.schema import IssueData, PaginationMeta


class AdminIssueQuery(BaseModel):
    search: str | None = Field(default=None, max_length=200)
    status: IssueStatusEnum | None = None
    category_id: str | None = Field(default=None, min_length=1)
    sort: Literal["newest", "oldest"] = "newest"
    page: int = Field(default=1, ge=1, le=2_147_483_647)
    limit: int = Field(default=10, ge=1, le=100)


class ReporterSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str | None


class AdminIssueData(IssueData):
    reporter: ReporterSummary | None = Field(validation_alias="citizen")


class AdminIssueResponse(BaseModel):
    message: str
    data: AdminIssueData


class AdminIssuePage(BaseModel):
    meta: PaginationMeta
    issues: list[AdminIssueData]


class AdminIssueListResponse(BaseModel):
    message: str
    data: AdminIssuePage
