import gzip
import json
from functools import cache
from pathlib import Path

from fastapi import HTTPException
from shapely import Point, STRtree
from shapely.geometry import shape
from sqlalchemy import String, cast, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nepal_location_models import District, LocalLevel

type AreaName = tuple[str, str]
type AreaNames = tuple[AreaName, ...]


@cache
def boundaries() -> tuple[STRtree, list[AreaNames], dict[AreaName, AreaNames]]:
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "nepal_report_boundaries.geojsonl.gz"
    )
    names: list[AreaNames] = []
    geometries = []
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for line in file:
            feature = json.loads(line)
            names.append(tuple(map(tuple, feature["properties"]["names"])))
            geometries.append(shape(feature["geometry"]))
    return (
        STRtree(geometries),
        names,
        {name: aliases for aliases in names for name in aliases},
    )


async def levels_by_name(
    db: AsyncSession, names: list[AreaName]
) -> dict[AreaName, str]:
    if not names:
        return {}
    rows = await db.execute(
        select(District.name, LocalLevel.name, LocalLevel.id)
        .join(LocalLevel, LocalLevel.district_id == District.id)
        .where(tuple_(District.name, LocalLevel.name).in_(names))
    )
    return {(district, name): str(level_id) for district, name, level_id in rows}


async def levels_at_pin(db: AsyncSession, latitude: float, longitude: float):
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(400, "Enter valid latitude and longitude.")
    tree, names, _ = boundaries()
    hits = tree.query(Point(longitude, latitude), predicate="covered_by")
    groups = [names[index] for index in hits]
    levels = await levels_by_name(db, [name for group in groups for name in group])
    return groups, levels


async def report_area_options(db: AsyncSession, latitude: float, longitude: float):
    groups, levels = await levels_at_pin(db, latitude, longitude)
    areas = []
    for group in sorted(groups):
        name = next((name for name in group if name in levels), None)
        if name is not None:
            areas.append({"id": levels[name], "name": name[1]})
    return areas


async def validate_report_area(
    db: AsyncSession,
    level_id: str | None,
    latitude: float | None,
    longitude: float | None,
) -> str:
    if not level_id or latitude is None or longitude is None:
        raise HTTPException(
            400, "Confirm the report municipality and both pin coordinates."
        )
    _, levels = await levels_at_pin(db, latitude, longitude)
    if level_id not in levels.values():
        raise HTTPException(400, "The pin must be inside the selected municipality.")
    return level_id


async def report_feed_area_ids(db: AsyncSession, level_id: str) -> list[str]:
    # Older catalogs may have a separate ID for the same municipality.
    rows = await db.execute(
        select(District.name, LocalLevel.name)
        .join(LocalLevel, LocalLevel.district_id == District.id)
        .where(cast(LocalLevel.id, String) == level_id)
    )
    row = rows.one_or_none()
    if row is None:
        return [level_id]
    _, _, aliases_by_name = boundaries()
    aliases = list(aliases_by_name.get((row[0], row[1]), ()))
    ids = await levels_by_name(db, aliases)
    return list({level_id, *ids.values()})
