from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import UserResponse, UpdateProfileRequest
from app.dependencies.auth_deps import get_current_user
from app.services.profile_service import update_profile
from app.core.database import get_db
from typing import Optional

router = APIRouter()


@router.get("/", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(current_user=Depends(get_current_user)):
    return {
        "message": "User fetched successfully",
        "data": current_user,
    }



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