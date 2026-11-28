from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enum import IssueStatusEnum
from app.schemas.schema import IssueData, Latitude, Longitude, PaginationMeta


class AdminIssueQuery(BaseModel):
    search: str | None = Field(default=None, max_length=200)
    status: IssueStatusEnum | None = None
    active_only: bool = False
    category_id: str | None = Field(default=None, min_length=1)
    sort: Literal["newest", "oldest", "upvotes"] = "newest"
    page: int = Field(default=1, ge=1, le=2_147_483_647)
    limit: int = Field(default=10, ge=1, le=100)
    south: Latitude | None = None
    north: Latitude | None = None
    west: Longitude | None = None
    east: Longitude | None = None

    @model_validator(mode="after")
    def validate_bounds(self):
        bounds = (self.south, self.north, self.west, self.east)
        if all(value is None for value in bounds):
            return self
        if any(value is None for value in bounds):
            raise ValueError("Provide south, north, west and east together.")
        if self.south > self.north or self.west > self.east:
            raise ValueError("Bounds must be ordered south to north and west to east.")
        return self


class ReporterSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str | None


class AdminIssueData(IssueData):
    upvote_count: int | None = None
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


class AdminIssueStatusTotals(BaseModel):
    open: int = 0
    in_progress: int = 0
    resolved: int = 0
    closed: int = 0


class AdminIssueStatusTotalsResponse(BaseModel):
    data: AdminIssueStatusTotals
