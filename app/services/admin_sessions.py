from hashlib import sha256
from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_auth import AdminMembership, AdminSession
from app.models.models import User
from app.schemas.admin_auth import AdminProfile
from app.schemas.enum import AccountStatusEnum


def digest_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


async def get_admin_profile(db: AsyncSession, user: User) -> AdminProfile:
    membership = await db.get(AdminMembership, user.id)
    if (
        not membership
        or user.account_status != AccountStatusEnum.active
        or user.deleted_at is not None
    ):
        raise HTTPException(403, "Admin permission required")
    return AdminProfile(email=user.email, name=user.name, role=membership.role)


async def revoke_session(db: AsyncSession, token: str | None):
    if token:
        await db.execute(
            delete(AdminSession).where(AdminSession.token_digest == digest_token(token))
        )


async def create_session(db: AsyncSession, user: User, previous_token: str | None) -> str:
    await get_admin_profile(db, user)
    await revoke_session(db, previous_token)
    token = token_urlsafe(32)
    db.add(AdminSession(token_digest=digest_token(token), user_id=user.id))
    await db.commit()
    return token


async def get_session_profile(db: AsyncSession, token: str | None) -> AdminProfile:
    if not token:
        raise HTTPException(401, "Admin sign-in required")
    user = await db.scalar(
        select(User)
        .join(AdminSession, AdminSession.user_id == User.id)
        .where(
            AdminSession.token_digest == digest_token(token),
            AdminSession.expires_at == 0,
        )
    )
    if user is None:
        raise HTTPException(401, "Admin sign-in required")
    return await get_admin_profile(db, user)
