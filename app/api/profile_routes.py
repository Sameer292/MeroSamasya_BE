from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import UserResponse, UpdateProfileRequest
from app.services.profile_service import update_profile
from app.services.location_service import serialize_user
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


@router.get("/", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_profile(
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await serialize_user(db, current_user, "Profile fetched successfully")


@router.patch("/", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_user_profile(
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    location_id: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = UpdateProfileRequest(
        name=name,
        phone=phone,
        location_id=location_id,
    )
    return await update_profile(current_user, data, profile_picture, db)
