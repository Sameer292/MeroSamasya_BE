import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    admin_auth_routes,
    admin_issue_moderation_routes,
    admin_issue_routes,
    admin_routes,
    admin_subscriber_routes,
    all_nepal_location_routes,
    auth_routes,
    category_routes,
    files_routes,
    issue_routes,
    kyc_routes,
    location_routes,
    notification_routes,
)
from app.core.admin_config import ADMIN_WEB_ORIGIN
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.migrations import backfill_report_areas, run_startup_migrations
from app.services.category_service import ensure_default_categories
from app.services.kyc_service import import_legacy_kyc_documents
from app.services.nepal_location_service import ensure_bundled_locations
from app.services.photo_storage import retire_deleted_report_photos, retry_photo_cleanup
from app.services.report_area_service import boundaries


@asynccontextmanager
async def lifespan(app: FastAPI):
    boundaries()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_startup_migrations(engine)
    async with AsyncSessionLocal() as session:
        await import_legacy_kyc_documents(session)
        await ensure_default_categories(session)
        await ensure_bundled_locations(session)
        await backfill_report_areas(session)
        await retire_deleted_report_photos(session)
    cleanup_worker = asyncio.create_task(retry_photo_cleanup())
    try:
        yield
    finally:
        cleanup_worker.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_worker


app = FastAPI(
    title="MeroSamasya",
    description="MeroSamasya backend API",
    version="0.0.1",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
    contact={
        "name": "MeroSamasya",
        "url": "https://github.com/sameer292/merosamasya_be",
    },
)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, error: RequestValidationError):
    # Input and context can include credentials or values JSON cannot encode.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {key: issue[key] for key in ("loc", "msg", "type")}
                for issue in error.errors()
            ]
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[ADMIN_WEB_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/", tags=["Root"])
def root():
    return {"message": "Working"}


app.include_router(admin_auth_routes.router, prefix="/api/auth/admin", tags=["Admin Authentication"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["Admin"])
app.include_router(admin_issue_routes.router, prefix="/api/admin/issues", tags=["Admin Issues"])
app.include_router(
    admin_subscriber_routes.router, prefix="/api/admin/subscribers", tags=["Admin Subscribers"]
)
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(
    admin_issue_moderation_routes.router, prefix="/api/admin/issues", tags=["Admin Issues"]
)
app.include_router(issue_routes.router, prefix="/api/issues", tags=["Issues"])
app.include_router(location_routes.router, prefix="/api/location", tags=["Location"])
app.include_router(files_routes.router, prefix="/api/files", tags=["Files"])
app.include_router(
    notification_routes.router, prefix="/api/notifications", tags=["Notifications"]
)
app.include_router(kyc_routes.router, prefix="/api/kyc", tags=["KYC"])
app.include_router(
    all_nepal_location_routes.router, prefix="/api/nepal", tags=["Nepal Location"]
)

app.include_router(category_routes.router, prefix="/api/category", tags=["Category"])
