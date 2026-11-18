from typing import Literal

from pydantic import BaseModel, EmailStr


class AdminProfile(BaseModel):
    email: EmailStr
    name: str | None
    role: Literal["admin", "superadmin"]


class AdminProfileResponse(BaseModel):
    data: AdminProfile
