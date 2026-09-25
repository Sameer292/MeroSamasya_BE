from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models.nepal_location_models import (
    Province,
    District,
    LocalLevel,
    LocalLevelType,
)

TYPE_MAPPING = {
    "Ma.Na.Pa.": LocalLevelType.MA_NA_PA,
    "Upa.Ma.": LocalLevelType.UPA_MA,
    "Na.Pa.": LocalLevelType.NA_PA,
    "Ga.Pa.": LocalLevelType.GA_PA,
}


async def seed_locations(data: dict, db: AsyncSession):
    try:
        for province_name, districts in data.items():
            province = Province(name=province_name)

            db.add(province)
            await db.flush()

            for district_name, local_types in districts.items():
                district = District(
                    name=district_name,
                    province_id=province.id,
                )

                db.add(district)
                await db.flush()

                for local_type, local_levels in local_types.items():
                    try:
                        level_type = TYPE_MAPPING[local_type]
                    except KeyError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unknown local level type: {local_type}",
                        )
                    for local_level_name in local_levels:
                        local_level = LocalLevel(
                            name=local_level_name,
                            type=level_type,
                            district_id=district.id,
                        )

                        db.add(local_level)

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Location data already seeded.",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed locations.",
        )
