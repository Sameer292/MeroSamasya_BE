from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import LocationResponse
from app.services.location_service import get_locations
from app.core.database import get_db

router = APIRouter()


@router.get(
    "/locations", response_model=list[LocationResponse], status_code=status.HTTP_200_OK
)
async def locations(db: AsyncSession = Depends(get_db)):
    return await get_locations(db)
