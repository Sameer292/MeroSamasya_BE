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
from fastapi import HTTPException, status
from email_validator import validate_email, EmailNotValidError

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
        try:
            email_info = validate_email(user.email, check_deliverability=True)
            email = email_info.normalized
        except EmailNotValidError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address")

        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        new_user = User(
            email=email,
            name=user.name,
            password=hash_password(user.password),
            phone=user.phone,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {"message": "User registered successfully", "user_id": new_user.id}

    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed. Please try again.")


async def login_user(user: UserLogin, db: AsyncSession):
    try:
        result = await db.execute(select(User).where(User.email == user.email))
        db_user = result.scalar_one_or_none()

        if not db_user or not verify_password(user.password, db_user.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        if db_user.account_status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not active")

        return {
            "access_token": create_token(db_user.id),
            "refresh_token": create_token(db_user.id, refresh=True),
            "user_id": db_user.id,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed. Please try again.")


async def refresh_access_token(token: str):
    try:
        payload = decode_token(token)

        if not payload.get("refresh"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = payload.get("sub")
        return {
            "access_token": create_token(user_id),
            "refresh_token": create_token(user_id, refresh=True),
            "user_id": user_id,
        }

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to refresh token")