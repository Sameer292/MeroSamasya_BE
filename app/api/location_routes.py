from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import LocationResponse, UpdateLocationRequest, UserResponse
from app.services.location_service import get_locations, update_user_location
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


@router.get(
    "/locations", response_model=list[LocationResponse], status_code=status.HTTP_200_OK
)
async def locations(db: AsyncSession = Depends(get_db)):
    return await get_locations(db)


@router.patch("/location", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_location(
    request: UpdateLocationRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_user_location(current_user, request.location_id, db)
