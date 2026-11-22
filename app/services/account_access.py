from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.schemas.enum import AccountStatusEnum


def require_active_account(user: User | None) -> User:
    if user is None or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if user.account_status == AccountStatusEnum.deleted:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if user.account_status != AccountStatusEnum.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account not active")
    return user


async def lock_active_account(db: AsyncSession, user_id: str) -> None:
    # Serialize citizen writes with deletion, including on SQLite (no FOR UPDATE).
    active_id = await db.scalar(
        update(User.__table__)
        .where(User.id == user_id, User.deleted_at.is_(None),
               User.account_status == AccountStatusEnum.active)
        .values(updated_at=User.updated_at)
        .returning(User.id)
    )
    if active_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
