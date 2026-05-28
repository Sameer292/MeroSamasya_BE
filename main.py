from fastapi import FastAPI
from app.api import problem_routes
from contextlib import asynccontextmanager
from app.api import (
    all_nepal_location_routes,
    auth_routes,
    issue_routes,
    location_routes,
)
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


app.include_router(auth_routes.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(issue_routes.router, prefix="/api/issues", tags=["Issues"])
app.include_router(location_routes.router, prefix="/api/location", tags=["Location"])
app.include_router(
    all_nepal_location_routes.router, prefix="/api/nepal", tags=["Nepal Location"]
)

app.include_router(
    problem_routes.router,
    prefix="/api/problems",
    tags=["Problems & Votes"],
)