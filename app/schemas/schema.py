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


class LocationSchema(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True


class LocationResponse(BaseModel):
    message: str
    data: list[LocationSchema]


class UpdateLocationRequest(BaseModel):
    location_id: str


class UserData(BaseModel):
    id: str
    email: EmailStr
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[LocationSchema] = None
    profile_picture_url: Optional[str] = None
    account_status: AccountStatusEnum
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    message: str
    data: UserData


class RegisterData(BaseModel):
    user_id: str


class RegisterResponse(BaseModel):
    message: str
    data: RegisterData


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str


class TokenResponse(BaseModel):
    message: str
    data: TokenData


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CategoryResponse(BaseModel):
    id: str
    name: str
    icon: str
    color: str

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    message: str
    data: list[CategoryResponse]


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


class IssueData(BaseModel):
    id: str
    citizen_id: Optional[str] = None
    category: Optional[CategoryResponse] = None
    title: str
    description: Optional[str] = None
    status: IssueStatusEnum
    latitude: float
    longitude: float
    address: Optional[str] = None
    media: list[IssueMediaResponse] = []
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IssueResponse(BaseModel):
    message: str
    data: IssueData


class IssueListData(BaseModel):
    total: int
    issues: list[IssueData]


class IssueListResponse(BaseModel):
    message: str
    data: IssueListData


class LocationListResponse(BaseModel):
    message: str
    data: list[LocationResponse]


class DeleteData(BaseModel):
    id: str


class DeleteResponse(BaseModel):
    message: str
    data: DeleteData
