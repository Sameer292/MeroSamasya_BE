from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User, Location
from fastapi import HTTPException, status


async def get_locations(db: AsyncSession):
    try:
        result = await db.execute(select(Location))
        return result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch locations",
        )


async def update_user_location(user: User, location_id: str, db: AsyncSession):
    try:
        user.location_id = location_id
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location",
        )
    return user