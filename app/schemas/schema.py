from pydantic import BaseModel, EmailStr, field_validator, Field, model_validator
from typing import Annotated, Optional
from datetime import datetime
from .enum import AccountStatusEnum, IssueStatusEnum
import re

FullName = Annotated[
    str,
    Field(
        min_length=2,
        max_length=50,
        pattern=r"^[a-zA-Z\s]+$",
        description="Letters and spaces only",
        examples=["Bishal Baniya"],
    ),
]
PhoneNumber = Annotated[
    str,
    Field(
        pattern=r"^[0-9]{10}$",
        description="Number must be 10 digits",
        examples=["9800000000"],
    ),
]


class UserCreate(BaseModel):
    name: FullName
    phone: PhoneNumber
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class LocationResponse(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True


class UpdateLocationRequest(BaseModel):
    location_id: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    phone: str
    location: Optional[LocationResponse]
    profile_picture_url: Optional[str]
    account_status: AccountStatusEnum
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    message: str
    user_id: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class IssueCreate(BaseModel):
    category_id: str
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    latitude: float
    longitude: float
    address: Optional[str] = None


class IssueMediaResponse(BaseModel):
    id: str
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


class IssueResponse(BaseModel):
    id: str
    citizen_id: str
    category_id: str
    title: str
    description: Optional[str]
    status: IssueStatusEnum
    latitude: float
    longitude: float
    address: Optional[str]
    media: list[IssueMediaResponse] = []
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class IssueListResponse(BaseModel):
    total: int
    issues: list[IssueResponse]