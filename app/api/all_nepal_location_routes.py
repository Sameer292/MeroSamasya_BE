from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.nepal_location_service import seed_locations
from app.schemas.nepal_location_schems import (
    DistrictResponse,
    LocalLevelResponse,
    ProvinceResponse,
)
from app.models.nepal_location_models import (
    District,
    LocalLevel,
    LocalLevelType,
    Province,
)

router = APIRouter()


@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_location_data(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    await seed_locations(data, db)
    return {"message": "Locations seeded successfully"}


@router.get(
    "/provinces",
    response_model=list[ProvinceResponse],
)
async def get_provinces(
    db: AsyncSession = Depends(get_db),
):
    provinces = await db.execute(select(Province))
    return provinces.scalars().all()


@router.get(
    "/provinces/{province_id}/districts",
    response_model=list[DistrictResponse],
)
async def get_districts(
    province_id: int,
    db: AsyncSession = Depends(get_db),
):
    districts_result = await db.execute(
        select(District).where(District.province_id == province_id)
    )
    districts = districts_result.scalars().all()
    if not districts:
        return []
    print(districts)
    return districts


@router.get(
    "/districts/{district_id}/local",
    response_model=list[LocalLevelResponse],
)
async def get_local_levels(
    district_id: int,
    type: LocalLevelType | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(LocalLevel).where(LocalLevel.district_id == district_id)

    if type:
        query = query.filter(LocalLevel.type == type)
    res = await db.execute(query)

    return res.scalars().all()
