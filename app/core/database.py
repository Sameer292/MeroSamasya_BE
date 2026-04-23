import os
from supabase import create_client
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

load_dotenv(".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_auth = create_client(SUPABASE_URL, SUPABASE_KEY)

DATABASE_URL = os.getenv("DATABASE_URL")
 
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"statement_cache_size": 0}
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
 
class Base(DeclarativeBase):
    pass
 
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session