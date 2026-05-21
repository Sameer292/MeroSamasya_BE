from sqlalchemy.ext.asyncio import AsyncSession
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
                for local_level_name in local_levels:
                    local_level = LocalLevel(
                        name=local_level_name,
                        type=TYPE_MAPPING[local_type],
                        district_id=district.id,
                    )

                    db.add(local_level)

    await db.commit()
