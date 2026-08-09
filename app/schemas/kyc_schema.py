from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.enum import KYCStatusEnum


class KYCSubmitResponse(BaseModel):
    message: str
    data: dict


class KYCStatusResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    date_of_birth: date
    citizenship_number: str
    citizenship_front_url: str
    citizenship_back_url: str
    selfie_url: str
    status: KYCStatusEnum
    rejection_reason: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KYCAdminListItem(BaseModel):
    id: str
    user_id: str
    full_name: str
    citizenship_number: str
    status: KYCStatusEnum
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KYCReviewRequest(BaseModel):
    action: KYCStatusEnum = Field(
        ...,
        description="Must be 'approved' or 'rejected'",
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Required when action is 'rejected'",
    )