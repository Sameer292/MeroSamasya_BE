from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user
from app.schemas.schema import (
    Latitude,
    LocationResponse,
    Longitude,
    UpdateLocationRequest,
    UserResponse,
)
from app.services.location_service import get_locations, update_user_location
from app.services.report_area_service import report_area_options

router = APIRouter()


@router.get(
    "/locations", response_model=LocationResponse, status_code=status.HTTP_200_OK
)
async def locations(
    district_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
):
    return await get_locations(db, district_id)


@router.get("/report-areas", response_model=LocationResponse)
async def report_areas(
    latitude: Latitude,
    longitude: Longitude,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return {
        "message": "Report municipalities fetched successfully",
        "data": await report_area_options(db, latitude, longitude),
    }


@router.patch("/location", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_location(
    request: UpdateLocationRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_user_location(current_user, request.location_id, db)
