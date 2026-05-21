from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.auth_routes import router as auth_routes
from app.api.issue_routes import router as issue_routes
from app.api.location_routes import router as location_routes
from app.api import auth_routes
from app.api import all_nepal_location_routes
from app.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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


@app.get("/", tags=["Root"])
def root():
    return {"message": "Working"}


app.include_router(auth_routes, prefix="/api/auth", tags=["Authentication"])
app.include_router(issue_routes, prefix="/api/issues", tags=["Issues"])
app.include_router(location_routes, prefix="/api/location", tags=["Location"])
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(
    all_nepal_location_routes.router,
    prefix="/api/nepal",
    tags=["Nepal Location"],
)
