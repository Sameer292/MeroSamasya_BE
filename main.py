from fastapi import FastAPI
from app.api.v1 import auth, user
from app.core.database import engine, Base

app = FastAPI(
    title="MeroSamasya",
    description="MeroSamasya backend API",
    version="0.0.1",
    swagger_ui_parameters={"persistAuthorization": True},
    contact={
        "name": "MeroSamasya",
        "url": "https://github.com/sameer292/merosamasya_be",
    },
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(user.router, prefix="/api/v1/user", tags=["User"])

@app.get("/", tags=["Root"])
def root():
    return {"message": "Working"}