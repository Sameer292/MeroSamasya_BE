from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User
from app.schemas.schema import UpdateProfileRequest
from fastapi import HTTPException, status, UploadFile
from app.core.cloudinary import upload_profile_picture
from typing import Optional

async def update_profile(
    user: User,
    data: UpdateProfileRequest,
    profile_picture: Optional[UploadFile],
    db: AsyncSession,
):
    try:
        if data.name is not None:
            user.name = data.name
        if data.phone is not None:
            user.phone = data.phone
        if data.location_id is not None:
            user.location_id = data.location_id
        if profile_picture is not None:
            file_bytes = await profile_picture.read()
            url = await upload_profile_picture(file_bytes, user.id)
            user.profile_picture_url = url

        await db.commit()

        result = await db.execute(
            select(User).where(User.id == user.id).options(selectinload(User.location))
        )
        updated_user = result.scalar_one_or_none()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile.",
        )

    return {
        "message": "Profile updated successfully",
        "data": updated_user,
    }
