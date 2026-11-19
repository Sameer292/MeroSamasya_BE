from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.admin_auth import AdminSession
from app.models.models import User
from app.models.refresh_token import RefreshToken
from app.schemas.enum import AccountStatusEnum
from app.schemas.password_change import CitizenPasswordChangeRequest
from app.schemas.password_policy import validate_password_strength
from app.services.auth_service import hash_password, verify_password


def validate_new_password(request: CitizenPasswordChangeRequest) -> str:
    password = request.new_password.get_secret_value()
    if (
        request.confirm_new_password is not None
        and password != request.confirm_new_password.get_secret_value()
    ):
        raise HTTPException(400, "New passwords do not match")
    if password == request.current_password.get_secret_value():
        raise HTTPException(400, "New password must differ from the current password")
    try:
        return validate_password_strength(password)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


async def replace_password(db: AsyncSession, user: User, password_hash: str) -> None:
    updated_id = await db.scalar(
        update(User)
        .where(
            User.id == user.id,
            User.password == user.password,
            User.account_status == AccountStatusEnum.active,
            User.deleted_at.is_(None),
        )
        .values(password=password_hash)
        .returning(User.id)
    )
    if updated_id is None:
        raise HTTPException(409, "Account changed during password update. Please retry.")
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == updated_id))
    await db.execute(delete(AdminSession).where(AdminSession.user_id == updated_id))
    await db.commit()


async def change_password(db: AsyncSession, user: User, request: CitizenPasswordChangeRequest):
    password = validate_new_password(request)
    if not await run_in_threadpool(
        verify_password, request.current_password.get_secret_value(), user.password
    ):
        raise HTTPException(400, "Current password is incorrect")
    password_hash = await run_in_threadpool(hash_password, password)
    await replace_password(db, user, password_hash)
