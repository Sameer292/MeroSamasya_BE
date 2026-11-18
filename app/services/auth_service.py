from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.models import User
from app.schemas.schema import UserCreate, UserLogin
from app.services.account_access import require_active_account
from app.services.refresh_tokens import issue_token_pair

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def normalize_registration_email(email: str) -> str:
    try:
        return validate_email(email, check_deliverability=True).normalized
    except EmailNotValidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address"
        )


async def create_registered_user(user: UserCreate, email: str, db: AsyncSession) -> User:
    try:
        new_user = User(
            email=email,
            name=user.name,
            password=hash_password(user.password),
            phone=user.phone,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )
    return new_user


async def register_user(user: UserCreate, db: AsyncSession):
    email = normalize_registration_email(user.email)
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    new_user = await create_registered_user(user, email, db)
    return {
        "message": "User registered successfully",
        "data": {"user_id": new_user.id},
    }


async def authenticate_user(user: UserLogin, db: AsyncSession):
    try:
        result = await db.execute(select(User).where(User.email == user.email))
        db_user = result.scalar_one_or_none()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again.",
        )

    if not db_user or not await run_in_threadpool(
        verify_password, user.password, str(db_user.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    return require_active_account(db_user)


async def login_user(user: UserLogin, db: AsyncSession):
    db_user = await authenticate_user(user, db)
    return {
        "message": "Login successful",
        "data": await issue_token_pair(db, db_user.id),
    }
