from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.models import User
from app.schemas.schema import UserCreate, UserLogin
from app.services.account_access import require_active_account
from app.services.notification_service import notify
from app.services.refresh_tokens import issue_token_pair

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def normalize_registration_email(email: str) -> str:
    try:
        return validate_email(email, check_deliverability=False).normalized.lower()
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
        await db.flush()
        notify(
            db,
            str(new_user.id),
            "system",
            "Welcome to MeroSamasya",
            "Report issues in your area and track them here.",
        )
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
    existing = await db.scalar(
        select(User.id).where(func.lower(User.email) == email).limit(1)
    )
    if existing is not None:
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
        statement = (
            select(User)
            .where(func.lower(User.email) == user.email.lower())
            .order_by((User.email == user.email).desc())
            .limit(2)
            .with_for_update()
        )
        matches = (await db.scalars(statement)).all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again.",
        )

    # Older databases could contain multiple case variants of an address.
    db_user = matches[0] if matches and (len(matches) == 1 or matches[0].email == user.email) else None
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
