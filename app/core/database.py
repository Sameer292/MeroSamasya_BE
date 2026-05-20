import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.engine import make_url

load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

url = make_url(DATABASE_URL)
connect_args = {}

# Apply asyncpg-specific options only for PostgreSQL asyncpg
if url.drivername == "postgresql+asyncpg":
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args,)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
