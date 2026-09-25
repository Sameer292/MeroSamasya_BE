import json
from pathlib import Path

from sqlalchemy import select
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

BUNDLED_SEED_PATH = Path(__file__).parent.parent / "data" / "nepal_locations.json"


def load_bundled_seed() -> dict:
    with open(BUNDLED_SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


async def seed_locations(data: dict, db: AsyncSession):
    """Idempotent upsert of the nested province/district/level payload.

    Matches by name within each parent, so re-runs only fill gaps (e.g. the
    Rukum local levels missing from older databases) and never duplicate.
    """
    added = {"provinces": 0, "districts": 0, "local_levels": 0}
    try:
        for province_name, districts in data.items():
            province = (
                await db.execute(
                    select(Province).where(Province.name == province_name)
                )
            ).scalar_one_or_none()
            if province is None:
                province = Province(name=province_name)
                db.add(province)
                await db.flush()
                added["provinces"] += 1

            for district_name, local_types in districts.items():
                district = (
                    await db.execute(
                        select(District).where(
                            District.name == district_name,
                            District.province_id == province.id,
                        )
                    )
                ).scalar_one_or_none()
                if district is None:
                    district = District(
                        name=district_name,
                        province_id=province.id,
                    )
                    db.add(district)
                    await db.flush()
                    added["districts"] += 1

                for local_type, local_levels in local_types.items():
                    try:
                        level_type = TYPE_MAPPING[local_type]
                    except KeyError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unknown local level type: {local_type}",
                        )
                    for local_level_name in local_levels:
                        exists = (
                            await db.execute(
                                select(LocalLevel.id).where(
                                    LocalLevel.name == local_level_name,
                                    LocalLevel.district_id == district.id,
                                )
                            )
                        ).scalar_one_or_none()
                        if exists is None:
                            db.add(
                                LocalLevel(
                                    name=local_level_name,
                                    type=level_type,
                                    district_id=district.id,
                                )
                            )
                            added["local_levels"] += 1

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
    return added


async def ensure_bundled_locations(db: AsyncSession) -> dict:
    """Seed the bundled Nepal data; no-op when already complete.

    Always runs at startup so older databases also gain missing levels
    (e.g. the Rukum backfill). Name-matched upsert, never duplicates.
    Returns counts of rows added.
    """
    return await seed_locations(load_bundled_seed(), db)
