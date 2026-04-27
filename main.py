from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import auth
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

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])