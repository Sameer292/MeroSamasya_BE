from fastapi import HTTPException, status

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
