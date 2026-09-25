from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User
from app.models.nepal_location_models import LocalLevel
from fastapi import HTTPException, status


async def get_locations(
    db: AsyncSession, district_id: int | None = None
) -> dict:
    """Selectable areas from live local_levels data. IDs are strings and
    valid for PATCH /api/location/location (replaces hardcoded client IDs)."""
    try:
        query = select(LocalLevel).order_by(LocalLevel.name)
        if district_id is not None:
            query = query.where(LocalLevel.district_id == district_id)
        result = await db.execute(query)
        levels = result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch locations",
        )
    return {
        "message": "Locations fetched successfully",
        "data": [{"id": str(level.id), "name": level.name} for level in levels],
    }


async def location_schema(db: AsyncSession, location_id: str | None) -> dict | None:
    """Resolve a user's location_id to {id, name} from live local_levels data."""
    if not location_id:
        return None
    try:
        level_id = int(location_id)
    except (TypeError, ValueError):
        return None
    result = await db.execute(select(LocalLevel).where(LocalLevel.id == level_id))
    level = result.scalar_one_or_none()
    if not level:
        return None
    return {"id": str(level.id), "name": level.name}


async def serialize_user(db: AsyncSession, user: User, message: str) -> dict:
    return {
        "message": message,
        "data": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "location": await location_schema(db, user.location_id),
            "profile_picture_url": user.profile_picture_url,
            "account_status": user.account_status,
            "role": user.role,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "deleted_at": user.deleted_at,
        },
    }


async def get_level_or_404(location_id: str, db: AsyncSession) -> LocalLevel:
    try:
        level_id = int(location_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )
    result = await db.execute(select(LocalLevel).where(LocalLevel.id == level_id))
    level = result.scalar_one_or_none()
    if not level:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )
    return level


async def update_user_location(user: User, location_id: str, db: AsyncSession):
    level = await get_level_or_404(location_id, db)
    user_id = str(user.id)

    try:
        await db.execute(
            User.__table__.update()
            .where(User.id == user_id)
            .values(location_id=str(level.id))
        )
        await db.commit()
        db.expire_all()
        result = await db.execute(select(User).where(User.id == user_id))
        updated_user = result.scalar_one_or_none()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location",
        )

    return await serialize_user(db, updated_user, "Location updated successfully")
