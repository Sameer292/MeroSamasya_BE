import asyncio
from datetime import UTC, date, datetime, timedelta
from itertools import product
from math import hypot
from os import environ
from random import Random

from shapely import Point
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

# Register every app table with Base.metadata before rebuilding the catalog.
import main  # noqa: F401
from app.core.database import AsyncSessionLocal, Base, engine
from seeder.catalog import (
    ADMIN_EMAIL,
    APPROVED_COUNT,
    FIRST_NAMES,
    HETAUDA,
    LAST_NAMES,
    MAKWANPUR,
    REPORTER_COUNT,
    SITES,
    STATUS_COUNTS,
)
from app.models.admin_auth import AdminMembership
from app.models.models import Category, Issue, IssueMedia, KycDocument, KycSubmission, User
from app.models.nepal_location_models import District, LocalLevel
from app.schemas.enum import IssueStatusEnum, KycStatusEnum, UserRole
from app.services.auth_service import hash_password
from app.services.category_service import CATEGORIES
from app.services.issue_service import MAX_IMAGES
from seeder.assets import DemoPhotos, download_assets, sample_document
from app.services.report_area_service import boundaries
from seeder.report_examples import report_detail_photo, report_status_events
from seeder.demo_votes import build_demo_upvotes
from seeder.reports import REPORTS_BY_SITE

LOCATION_TABLES = {"provinces", "districts", "local_levels"}


def resettable_tables():
    return [table for table in Base.metadata.sorted_tables if table.name not in LOCATION_TABLES]


async def clear_app_tables(db: AsyncSession) -> None:
    connection = await db.connection()
    tables = resettable_tables()
    if connection.dialect.name == "postgresql":
        await db.execute(text("SET LOCAL search_path TO public"))
        await db.execute(text("SET LOCAL lock_timeout = '10s'"))
    await connection.run_sync(Base.metadata.create_all)
    if connection.dialect.name == "postgresql":
        quote = connection.dialect.identifier_preparer.quote
        qualified = ", ".join(f"public.{quote(table.name)}" for table in tables)
        await db.execute(text(f"TRUNCATE TABLE {qualified} RESTART IDENTITY RESTRICT"))
    elif connection.dialect.name == "sqlite":
        for table in reversed(tables):
            await db.execute(table.delete())
    else:
        raise ValueError("The demo seeder supports PostgreSQL and SQLite.")


async def load_hetauda(db: AsyncSession) -> LocalLevel:
    hetauda = await db.scalar(
        select(LocalLevel)
        .join(LocalLevel.district)
        .where(District.name == MAKWANPUR, LocalLevel.name == HETAUDA)
        .options(joinedload(LocalLevel.district).joinedload(District.province))
    )
    if hetauda is None:
        raise ValueError("Hetauda is missing from the target location catalog. Initialize the app first.")
    return hetauda


def build_citizen(index, first, last, password_hash, location_id, avatar_url, now):
    email = "ram" if index == 0 else f"{first.lower()}.{last.lower()}"
    joined = now - timedelta(days=150 + index % 55)
    return User(
        email=f"{email}@example.com", name=f"{first} {last}", password=password_hash,
        phone=f"980000{index + 1:04d}", location_id=location_id, profile_picture_url=avatar_url,
        created_at=joined, updated_at=joined,
    )


async def seed_accounts(db, location_id, avatars, photos, now):
    password_hash = hash_password(environ["SEED_DEMO_PASSWORD"])
    citizens = []
    names = product(LAST_NAMES, FIRST_NAMES)
    for index, (last, first) in enumerate(names):
        avatar = photos.add(db, "profiles", avatars[index % len(avatars)])
        citizens.append(build_citizen(index, first, last, password_hash, location_id, avatar, now))
    admin = User(
        email=ADMIN_EMAIL, name="Hetauda Demo Admin", password=password_hash,
        location_id=location_id, profile_picture_url=photos.add(db, "profiles", avatars[-1]),
        created_at=now - timedelta(days=210), updated_at=now - timedelta(days=210),
    )
    db.add_all([*citizens, admin])
    await db.flush()
    db.add(AdminMembership(user_id=admin.id, role=UserRole.admin.value))
    return citizens, admin.id


def build_submission(index, citizen, location, now):
    status = KycStatusEnum.approved
    if index >= APPROVED_COUNT:
        status = KycStatusEnum.pending if index < 90 else KycStatusEnum.rejected
    submitted = now - timedelta(days=100 + index % 35 if index < APPROVED_COUNT else index - 78)
    return KycSubmission(
        user_id=citizen.id, full_name=citizen.name, citizenship_number=f"DEMO-HTD-{index + 1:04d}",
        gender=("male", "female", "female", "male", "female", "male", "female", "male", "female", "male")[index % 10],
        date_of_birth=date(1980 + index % 23, 1 + index % 12, 1 + index % 27),
        issued_date=date(2017 + index % 4, 1 + index % 12, 1 + index % 26),
        ward_number=str(index % 19 + 1), tole=SITES[index % len(SITES)][0],
        municipality_name=location.name, district_name=location.district.name,
        province_name=location.district.province.name, local_level_id=str(location.id),
        status=status, created_at=submitted,
        updated_at=submitted if status == KycStatusEnum.pending else submitted + timedelta(days=1),
        reviewer_note="Demo rejection: please submit a clearer sample." if status == KycStatusEnum.rejected else None,
    )


async def seed_kyc(db, citizens, location, avatars, now) -> None:
    submissions = [build_submission(index, citizen, location, now)
                   for index, citizen in enumerate(citizens[:95])]
    db.add_all(submissions)
    await db.flush()
    for index, submission in enumerate(submissions):
        for kind in ("selfie", "front", "back"):
            data = sample_document(kind, submission.full_name, submission.citizenship_number,
                                   avatars[index % len(avatars)])
            db.add(KycDocument(submission_id=submission.id, kind=kind,
                               content_type="image/jpeg", data=data))


def pin_distance(first, second):
    # Scale longitude to account for Hetauda's latitude.
    return hypot(first[0] - second[0], (first[1] - second[1]) * 0.887)


def spread_report_pin(random, anchor, previous, tree, names):
    for _ in range(2_000):
        pin = tuple(coordinate + random.uniform(-0.011, 0.011) for coordinate in anchor)
        if any(pin_distance(pin, other) < 0.002 for other in previous):
            continue
        nearest = min((site[1:] for site in SITES), key=lambda site: pin_distance(pin, site))
        if nearest != anchor:
            continue
        latitude, longitude = pin
        matches = tree.query(Point(longitude, latitude), predicate="covered_by")
        if any((MAKWANPUR, HETAUDA) in names[hit] for hit in matches):
            return latitude, longitude
    raise ValueError(f"Could not place a separated Hetauda report near {anchor}")


def report_fixtures():
    statuses = [status for status, count in STATUS_COUNTS for _ in range(count)]
    tree, names, _ = boundaries()
    random = Random(209)
    previous = []
    combinations = [
        (anchor, report)
        for anchor in SITES
        for report in REPORTS_BY_SITE[anchor[0]]
    ]
    if len(combinations) != len(statuses):
        raise ValueError("The report catalog and status counts must describe the same number of issues.")
    for index, ((site, latitude, longitude), template) in enumerate(combinations):
        pin = spread_report_pin(random, (latitude, longitude), previous, tree, names)
        previous.append(pin)
        yield site, *pin, template, statuses[(index * 37) % len(statuses)]


def build_issue(index, fixture, owner, location_id, category, now) -> Issue:
    site, latitude, longitude, template, status = fixture
    created = now - timedelta(days=2 + index * 5 % 89, hours=index % 24)
    updated = created if status == IssueStatusEnum.open else created + timedelta(hours=18 + index % 17)
    return Issue(
        citizen_id=owner.id, category_id=category.id, local_level_id=location_id,
        title=template.title, description=template.description,
        status=status, latitude=latitude, longitude=longitude, address=f"{site}, Hetauda, Makwanpur",
        created_at=created, updated_at=updated,
        resolved_at=updated if status == IssueStatusEnum.resolved else None,
    )


def demo_report_assignments(citizens, random):
    reporters = random.sample(citizens[:APPROVED_COUNT], REPORTER_COUNT)
    # Most residents report once or not at all. A small group reports regularly.
    report_counts = [1] * 32 + [2] * 15 + [3] * 8 + [4] * 3 + [5] * 2
    owners = [
        citizen
        for citizen, count in zip(reporters, report_counts, strict=True)
        for _ in range(count)
    ]
    # Preserve the showcase total of 232 attachments while using the whole range.
    photo_counts = [1] * 24 + [2] * 44 + [MAX_IMAGES] * 40
    random.shuffle(owners)
    random.shuffle(photo_counts)
    return zip(owners, photo_counts, strict=True)


def add_report_media(db, issue, photo, count, photos) -> None:
    images = [photo] + [
        report_detail_photo(photo, inset_divisor=divisor)
        for divisor in (6, 4)[:count - 1]
    ]
    for content in images:
        url = photos.add(db, "issues", content)
        issue.media.append(IssueMedia(url=url, created_at=issue.created_at))


async def populate(db, location, fixtures, photo_bytes, avatars, photos) -> None:
    now = datetime.now(UTC)
    location_id = str(location.id)
    categories = {data["name"]: Category(**data) for data in CATEGORIES}
    db.add_all(categories.values())
    citizens, reviewer_id = await seed_accounts(db, location_id, avatars, photos, now)
    await seed_kyc(db, citizens, location, avatars, now)
    voter_ids = [citizen.id for citizen in citizens[:APPROVED_COUNT]]
    issues = []
    assignments = demo_report_assignments(citizens, Random(421))
    for index, (fixture, (owner, photo_count)) in enumerate(zip(fixtures, assignments, strict=True)):
        template = fixture[3]
        issue = build_issue(index, fixture, owner, location_id, categories[template.category], now)
        add_report_media(db, issue, photo_bytes[template.photo], photo_count, photos)
        issues.append(issue)
        db.add(issue)
        db.add_all(build_demo_upvotes(issue, index, voter_ids))
    await db.flush()

    db.add_all(event for issue in issues for event in report_status_events(issue, reviewer_id))


async def reset_and_seed() -> str:
    fixtures = list(report_fixtures())
    print("Preparing public demo images before connecting to the database.", flush=True)
    photo_bytes, avatars = await asyncio.to_thread(download_assets)
    photos = DemoPhotos()
    try:
        async with AsyncSessionLocal.begin() as db:
            location = await load_hetauda(db)
            await clear_app_tables(db)
            await populate(db, location, fixtures, photo_bytes, avatars, photos)
            await asyncio.to_thread(photos.write)
    except BaseException:
        photos.discard()
        raise
    finally:
        await engine.dispose()
    return f"Seeded 100 citizens, 1 admin, 95 KYC submissions, and {len(fixtures)} Hetauda issues."
