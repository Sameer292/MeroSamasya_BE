from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User, Location
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
    if data.location_id is not None:
        location_result = await db.execute(
            select(Location).where(Location.id == data.location_id)
        )
        if not location_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found.",
            )

    user_id = str(user.id)
    values = {}

    if data.name is not None:
        values["name"] = data.name
    if data.phone is not None:
        values["phone"] = data.phone
    if data.location_id is not None:
        values["location_id"] = data.location_id
    if profile_picture is not None:
        file_bytes = await profile_picture.read()
        values["profile_picture_url"] = await upload_profile_picture(
            file_bytes, user_id
        )

    try:
        if values:
            await db.execute(
                User.__table__.update().where(User.id == user_id).values(**values)
            )
        await db.commit()
        db.expire_all()
        result = await db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.location))
        )
        updated_user = result.scalar_one_or_none()
    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile.",
        )

    return {
        "message": "Profile updated successfully",
        "data": updated_user,
    }
