from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProblemCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10)
    category: Optional[str] = None
    image_url: Optional[str] = None
    location_id: Optional[str] = None


class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=5, max_length=200)
    description: Optional[str] = Field(default=None, min_length=10)
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_resolved: Optional[bool] = None


class VoteResponse(BaseModel):
    message: str
    vote_count: int
    has_voted: bool


class ProblemAuthor(BaseModel):
    id: str
    name: str
    profile_picture_url: Optional[str]

    class Config:
        from_attributes = True


class ProblemResponse(BaseModel):
    id: str
    title: str
    description: str
    category: Optional[str]
    image_url: Optional[str]
    is_resolved: bool
    vote_count: int
    has_voted: bool
    user: ProblemAuthor
    location_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProblemListResponse(BaseModel):
    id: str
    title: str
    category: Optional[str]
    is_resolved: bool
    vote_count: int
    has_voted: bool
    user: ProblemAuthor
    location_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedProblems(BaseModel):
    total: int
    page: int
    page_size: int
    problems: list[ProblemListResponse]