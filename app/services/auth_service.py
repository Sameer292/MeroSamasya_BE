import uuid
import jwt
import os
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User
from app.schemas.schema import UserCreate, UserLogin
from dotenv import load_dotenv

load_dotenv(".env")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRY_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", 15))

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: str, refresh: bool = False) -> str:
    expiry = timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS) if refresh else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "refresh": refresh,
        "exp": datetime.now(timezone.utc) + expiry,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


async def register_user(user: UserCreate, db: AsyncSession):
    try:
        existing = await db.execute(select(User).where(User.email == user.email))
        if existing.scalar_one_or_none():
            return {"error": "Email already registered"}

        new_user = User(
            email=user.email,
            name=user.name,
            password=hash_password(user.password),
            phone=user.phone,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {"message": "User registered successfully", "user_id": new_user.id}

    except Exception as e:
        await db.rollback()
        return {"error": f"Registration failed: {str(e)}"}


async def login_user(user: UserLogin, db: AsyncSession):
    try:
        result = await db.execute(select(User).where(User.email == user.email))
        db_user = result.scalar_one_or_none()

        if not db_user or not verify_password(user.password, db_user.password):
            return {"error": "Invalid email or password"}

        if db_user.account_status != "active":
            return {"error": "Account not active"}

        return {
            "access_token": create_token(db_user.id),
            "refresh_token": create_token(db_user.id, refresh=True),
            "user_id": db_user.id,
        }

    except Exception as e:
        return {"error": "Login failed. Please try again."}


async def refresh_access_token(token: str):
    try:
        payload = decode_token(token)

        if not payload.get("refresh"):
            return {"error": "Invalid token type"}

        user_id = payload.get("sub")
        return {
            "access_token": create_token(user_id),
            "refresh_token": create_token(user_id, refresh=True),
            "user_id": user_id,
        }

    except jwt.ExpiredSignatureError:
        return {"error": "Refresh token expired"}
    except Exception:
        return {"error": "Failed to refresh token"}


async def get_user_from_token(token: str):
    try:
        payload = decode_token(token)
        if payload.get("refresh"):
            return None
        return payload
    except Exception:
        return None