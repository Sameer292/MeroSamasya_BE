from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.schemas.schema import UpdateProfileRequest
from app.services.image_upload import read_image_upload
from app.services.location_service import (
    get_level_or_404,
    serialize_user,
)
from app.services.photo_storage import change_photos


async def update_profile(
    user: User,
    data: UpdateProfileRequest,
    profile_picture: UploadFile | None,
    db: AsyncSession,
):
    # ponytail: snapshot id first, user expires after expire_all() below
    user_id = str(user.id)
    if data.location_id is not None:
        level = await get_level_or_404(data.location_id, db)
        location_id = str(level.id)
    else:
        location_id = None

    avatar = await read_image_upload(profile_picture, "profile_picture") if profile_picture else None

    values = {}
    if data.name is not None:
        values["name"] = data.name
    if data.phone is not None:
        values["phone"] = data.phone
    if location_id is not None:
        values["location_id"] = location_id
    try:
        async with change_photos(db) as photos:
            previous_avatar = None
            if avatar is not None:
                data_bytes, content_type = avatar
                values["profile_picture_url"] = await photos.upload(data_bytes, "profiles", content_type)
                if db.get_bind().dialect.name == "sqlite":
                    await db.execute(update(User.__table__).where(User.id == user_id)
                                     .values(updated_at=User.updated_at))
                previous_avatar = await db.scalar(
                    select(User.profile_picture_url).where(User.id == user_id).with_for_update()
                )
            if values:
                result = await db.execute(
                    update(User.__table__).where(User.id == user_id).values(**values)
                )
                if not result.rowcount:
                    raise HTTPException(status_code=404, detail="User not found.")
            if previous_avatar:
                await photos.retire(previous_avatar)
        db.expire_all()
        result = await db.execute(select(User).where(User.id == user_id))
        updated_user = result.scalar_one()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile.",
        )

    return await serialize_user(db, updated_user, "Profile updated successfully")
