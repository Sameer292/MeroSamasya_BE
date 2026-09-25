from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def run_startup_migrations(engine: AsyncEngine):
    """Idempotent data-compatibility fixes create_all cannot do.

    1. Old databases carry Users.location_id -> Locations.id FK metadata.
       ORM no longer declares it, but Postgres still enforces the stored
       constraint, which would reject local_levels ids. Drop it.
    2. Issues.local_level_id did not exist on old databases. Add it.
    3. Backfill it from the reporter's residence for pre-existing rows.
    Safe to run on every boot; each step is guarded/no-op when done.
    """
    backend = engine.url.get_backend_name()
    async with engine.begin() as conn:
        if backend == "postgresql":
            await conn.execute(
                text('ALTER TABLE "Users" DROP CONSTRAINT IF EXISTS users_location_id_fkey')
            )
            await conn.execute(
                text('ALTER TABLE "Issues" ADD COLUMN IF NOT EXISTS local_level_id VARCHAR')
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
        else:
            return
        # ponytail: no silent catch here, a backfill failure must crash
        # startup loudly instead of leaving half-migrated data behind.
        await conn.execute(
            text(
                'UPDATE "Issues" SET local_level_id = '
                '(SELECT location_id FROM "Users" WHERE "Users".id = "Issues".citizen_id) '
                'WHERE local_level_id IS NULL'
            )
        )
