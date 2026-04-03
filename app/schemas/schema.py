from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
from .enum import RoleEnum, AccountStatusEnum

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    phone: str
    role: RoleEnum
    profile_picture_url: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    middle_name: Optional[str]
    last_name: str
    phone: str
    role: RoleEnum
    profile_picture_url: Optional[str]
    account_status: AccountStatusEnum
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: UUID

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RegisterResponse(BaseModel):
    message: str
    user_id: UUID
