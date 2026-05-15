from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User, Location
from fastapi import HTTPException, status


async def get_locations(db: AsyncSession):
    try:
        result = await db.execute(select(Location))
        return {
            "message": "Locations fetched successfully",
            "data": result.scalars().all(),
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch locations",
        )


async def update_user_location(user: User, location_id: str, db: AsyncSession):
    try:
        user.location_id = location_id
        await db.commit()
        result = await db.execute(
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.location))
        )
        updated_user = result.scalar_one_or_none()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location",
        )

    return {
        "message": "Location updated successfully",
        "data": updated_user,
    }