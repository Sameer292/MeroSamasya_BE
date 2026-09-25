from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api import (
    admin_auth_routes,
    admin_issue_moderation_routes,
    admin_issue_routes,
    admin_subscriber_routes,
    all_nepal_location_routes,
    auth_routes,
    category_routes,
    files_routes,
    issue_routes,
    location_routes,
    notification_routes,
    kyc_routes,
    admin_routes,
)
from app.core.admin_config import ADMIN_WEB_ORIGIN
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.migrations import run_startup_migrations
from app.services.category_service import ensure_default_categories
from app.services.nepal_location_service import ensure_bundled_locations


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_startup_migrations(engine)
    async with AsyncSessionLocal() as session:
        await ensure_default_categories(session)
        await ensure_bundled_locations(session)
    yield


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
app.include_router(admin_routes.router, prefix="/api/admin", tags=["Admin"])
app.include_router(
    all_nepal_location_routes.router, prefix="/api/nepal", tags=["Nepal Location"]
)

app.include_router(category_routes.router, prefix="/api/category", tags=["Category"])
