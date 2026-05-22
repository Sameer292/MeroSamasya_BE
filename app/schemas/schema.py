from pydantic import BaseModel, EmailStr, field_validator, Field, model_validator
from typing import Annotated, Optional
from datetime import datetime
from .enum import AccountStatusEnum
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


class UpdateProfileRequest(BaseModel):
    name: Optional[FullName] = None
    phone: Optional[PhoneNumber] = None
    location_id: Optional[str] = None
    profile_picture_url: Optional[str] = None
