from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import  Location
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
