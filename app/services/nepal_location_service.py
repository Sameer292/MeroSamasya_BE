import json
from itertools import batched
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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


async def existing_ids(db: AsyncSession, table, keys):
    result = await db.execute(select(*keys, table.c.id))
    return {tuple(row[:-1]): row[-1] for row in result}


async def insert_missing(db: AsyncSession, table, keys, records):
    ids = await existing_ids(db, table, keys)
    missing = {}
    for record in records:
        key = tuple(record[column.name] for column in keys)
        if key not in ids:
            missing.setdefault(key, record)
    if not missing:
        return ids, 0

    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    added = 0
    for batch in batched(missing.values(), 300):
        statement = (
            insert(table).values(list(batch)).on_conflict_do_nothing(index_elements=keys)
            .returning(*keys, table.c.id)
        )
        rows = (await db.execute(statement)).all()
        ids.update({tuple(row[:-1]): row[-1] for row in rows})
        added += len(rows)
    # Another seeder may have inserted some keys between our read and insert.
    if added != len(missing):
        ids = await existing_ids(db, table, keys)
    return ids, added


def district_records(data, province_ids):
    for province_name, districts in data.items():
        for name in districts:
            yield {"name": name, "province_id": province_ids[(province_name,)]}


def local_level_records(data, province_ids, district_ids):
    for province_name, districts in data.items():
        province_id = province_ids[(province_name,)]
        for district_name, local_types in districts.items():
            district_id = district_ids[(district_name, province_id)]
            for local_type, names in local_types.items():
                level_type = TYPE_MAPPING.get(local_type)
                if level_type is None:
                    raise HTTPException(400, f"Unknown local level type: {local_type}")
                for name in names:
                    yield {"name": name, "type": level_type, "district_id": district_id}


async def seed_location_tables(data: dict, db: AsyncSession) -> dict:
    provinces, districts, levels = (model.__table__ for model in (Province, District, LocalLevel))
    province_ids, province_count = await insert_missing(
        db, provinces, (provinces.c.name,), ({"name": name} for name in data)
    )
    district_ids, district_count = await insert_missing(
        db, districts, (districts.c.name, districts.c.province_id),
        district_records(data, province_ids),
    )
    _, level_count = await insert_missing(
        db, levels, (levels.c.name, levels.c.district_id),
        local_level_records(data, province_ids, district_ids),
    )
    return {"provinces": province_count, "districts": district_count, "local_levels": level_count}


async def seed_locations(data: dict, db: AsyncSession) -> dict:
    """Add missing locations by name within their parent and preserve existing IDs."""
    try:
        added = await seed_location_tables(data, db)
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
    """Seed the bundled MoFAGA extract; additive only, never deletes.

    Fresh DBs get the full 7/77/753 dataset. Older databases only gain
    missing rows by name-match. A stale dev database (e.g. pre-official
    names) should be deleted once for a clean reseed; the file is gitignored
    and holds no users/issues. Returns counts of rows added.
    """
    return await seed_locations(load_bundled_seed(), db)
