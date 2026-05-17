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
    location_result = await db.execute(select(Location).where(Location.id == location_id))
    if not location_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )

    user_id = str(user.id)

    try:
        await db.execute(
            User.__table__.update().where(User.id == user_id).values(location_id=location_id)
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
            detail="Failed to update location",
        )

    return {
        "message": "Location updated successfully",
        "data": updated_user,
    }