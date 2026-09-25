from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, UploadFile
from app.models.models import User
from app.schemas.schema import UpdateProfileRequest
from app.services.location_service import (
    get_level_or_404,
    serialize_user,
)
from app.core.cloudinary import (
    upload_profile_picture,
    is_configured as cloudinary_configured,
)
from app.core.storage import save_local
from app.services.issue_service import (
    ALLOWED_TYPES,
    MAX_FILE_BYTES,
    check_file_bytes,
)


async def store_avatar(
    file_bytes: bytes, content_type: str | None, user_id: str
) -> str:
    # ponytail: Cloudinary when configured, local disk fallback otherwise
    if cloudinary_configured():
        return await upload_profile_picture(file_bytes, user_id)
    name = save_local(file_bytes, "profiles", content_type)
    return f"/api/files/profiles/{name}"


async def update_profile(
    user: User,
    data: UpdateProfileRequest,
    profile_picture: UploadFile | None,
    db: AsyncSession,
):
    if data.location_id is not None:
        level = await get_level_or_404(data.location_id, db)
        location_id = str(level.id)
    else:
        location_id = None

    avatar_url = None
    if profile_picture is not None:
        if profile_picture.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {profile_picture.content_type}.",
            )
        # ponytail: bounded read, a huge upload never fully lands in memory
        file_bytes = await profile_picture.read(MAX_FILE_BYTES + 1)
        check_file_bytes(file_bytes)
        avatar_url = await store_avatar(file_bytes, profile_picture.content_type, str(user.id))

    values = {}
    if data.name is not None:
        values["name"] = data.name
    if data.phone is not None:
        values["phone"] = data.phone
    if location_id is not None:
        values["location_id"] = location_id
    if avatar_url is not None:
        values["profile_picture_url"] = avatar_url

    try:
        if values:
            await db.execute(
                User.__table__.update().where(User.id == str(user.id)).values(**values)
            )
            await db.commit()
        db.expire_all()
        result = await db.execute(select(User).where(User.id == str(user.id)))
        updated_user = result.scalar_one()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile.",
        )

    return await serialize_user(db, updated_user, "Profile updated successfully")


async def change_password(
    user: User,
    current_password: str,
    new_password: str,
    db: AsyncSession,
):
    from app.services.auth_service import verify_password, hash_password

    result = await db.execute(select(User).where(User.id == str(user.id)))
    db_user = result.scalar_one()
    if not verify_password(current_password, str(db_user.password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    try:
        await db.execute(
            User.__table__
            .update()
            .where(User.id == str(user.id))
            .values(password=hash_password(new_password))
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password.",
        )
    return {"message": "Password changed successfully"}
