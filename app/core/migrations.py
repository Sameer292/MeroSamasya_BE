from datetime import date

from sqlalchemy import inspect, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.models.models import Issue
from app.services.report_area_service import report_area_options


async def limit_startup_lock_wait(conn: AsyncConnection) -> None:
    if conn.dialect.name == "postgresql":
        await conn.execute(text("SET LOCAL lock_timeout = '10s'"))


async def run_startup_migrations(engine: AsyncEngine):
    """Idempotent data-compatibility fixes create_all cannot do.

    1. Old databases carry Users.location_id -> Locations.id FK metadata.
       ORM no longer declares it, but Postgres still enforces the stored
       constraint, which would reject local_levels ids. Drop it.
    2. Issues.local_level_id did not exist on old databases. Add it.
    3. Restore the Categories.deleted_at column on older category databases.
    4. Give refresh-token records a stable session ID.
    5. Convert legacy KYC timestamps to Nepal calendar dates.
    6. Add account-scoped report submission IDs.
    Safe to run on every boot; each step is guarded/no-op when done.
    """
    backend = engine.url.get_backend_name()
    async with engine.begin() as conn:
        if backend == "postgresql":
            await limit_startup_lock_wait(conn)
            await conn.execute(
                text('ALTER TABLE "Users" DROP CONSTRAINT IF EXISTS users_location_id_fkey')
            )
            await conn.execute(
                text('ALTER TABLE "Users" DROP CONSTRAINT IF EXISTS "Users_location_id_fkey"')
            )
            await conn.execute(
                text('ALTER TABLE "Issues" ADD COLUMN IF NOT EXISTS local_level_id VARCHAR')
            )
            await conn.execute(
                text('ALTER TABLE "Issues" ADD COLUMN IF NOT EXISTS submission_id VARCHAR(36)')
            )
            await conn.execute(
                text('ALTER TABLE "Categories" ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP')
            )
            await conn.execute(
                text('ALTER TABLE "RefreshTokens" ADD COLUMN IF NOT EXISTS session_id VARCHAR(64)')
            )
        elif backend == "sqlite":
            cols = [
                row[1]
                for row in (await conn.execute(text('PRAGMA table_info("Issues")'))).all()
            ]
            if "local_level_id" not in cols:
                await conn.execute(
                    text('ALTER TABLE "Issues" ADD COLUMN local_level_id VARCHAR')
                )
            if "submission_id" not in cols:
                await conn.execute(
                    text('ALTER TABLE "Issues" ADD COLUMN submission_id VARCHAR(36)')
                )
            category_cols = await conn.execute(text('PRAGMA table_info("Categories")'))
            if "deleted_at" not in [row[1] for row in category_cols]:
                await conn.execute(
                    text('ALTER TABLE "Categories" ADD COLUMN deleted_at DATETIME')
                )
            token_cols = await conn.execute(text('PRAGMA table_info("RefreshTokens")'))
            if "session_id" not in [row[1] for row in token_cols]:
                await conn.execute(
                    text('ALTER TABLE "RefreshTokens" ADD COLUMN session_id VARCHAR(64)')
                )
        if backend in ("postgresql", "sqlite"):
            await conn.execute(
                text('CREATE UNIQUE INDEX IF NOT EXISTS ix_issues_citizen_submission '
                     'ON "Issues" (citizen_id, submission_id)')
            )
            await conn.execute(
                text('CREATE UNIQUE INDEX IF NOT EXISTS "ix_RefreshTokens_session_id" '
                     'ON "RefreshTokens" (session_id)')
            )
        kyc_date_columns = ("date_of_birth", "issued_date")
        if backend == "postgresql":
            await conn.execute(text('LOCK TABLE "KycSubmissions" IN ACCESS EXCLUSIVE MODE'))
            columns = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_columns("KycSubmissions")
            )
            for column in columns:
                name = column["name"]
                if name in kyc_date_columns and column["type"].python_type is not date:
                    await conn.execute(text(
                        f'ALTER TABLE "KycSubmissions" ALTER COLUMN {name} TYPE DATE '
                        f"USING ({name} AT TIME ZONE 'Asia/Kathmandu')::date"
                    ))
        elif backend == "sqlite":
            # SQLite stores DATE as ISO text. Recover the local day from legacy UTC times.
            for name in kyc_date_columns:
                await conn.execute(text(
                    f'UPDATE "KycSubmissions" SET {name} = date({name}, '
                    f"CASE WHEN {name} < '1985-12-31 18:30' THEN '+05:30' ELSE '+05:45' END) "
                    f"WHERE length({name}) > 10"
                ))


async def backfill_report_areas(db: AsyncSession):
    issues = await db.execute(
        select(Issue.id, Issue.latitude, Issue.longitude)
        .where(Issue.local_level_id.is_(None))
    )
    for issue_id, latitude, longitude in issues:
        if latitude is None or longitude is None:
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        areas = await report_area_options(db, latitude, longitude)
        if len(areas) == 1:
            await db.execute(
                update(Issue.__table__)
                .where(Issue.id == issue_id, Issue.local_level_id.is_(None))
                .values(local_level_id=areas[0]["id"], updated_at=Issue.updated_at)
            )
    await db.commit()
