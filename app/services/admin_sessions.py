from hashlib import sha256
from secrets import token_urlsafe
from time import time

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_auth import AdminMembership, AdminSession
from app.models.models import User
from app.schemas.admin_auth import AdminProfile
from app.schemas.enum import AccountStatusEnum
from app.services.auth_service import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRY_DAYS

SESSION_MAX_AGE = REFRESH_TOKEN_EXPIRY_DAYS * 86400
ACCESS_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60


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
    now = int(time())
    await db.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
    db.add(AdminSession(
        token_digest=digest_token(token),
        user_id=user.id,
        access_expires_at=min(now + ACCESS_MAX_AGE, now + SESSION_MAX_AGE),
        expires_at=now + SESSION_MAX_AGE,
    ))
    await db.commit()
    return token


async def get_session(db: AsyncSession, token: str | None, *, allow_refresh: bool = False):
    if not token:
        raise HTTPException(401, "Admin session required")
    result = await db.execute(
        select(AdminSession, User)
        .join(User, AdminSession.user_id == User.id)
        .where(AdminSession.token_digest == digest_token(token))
    )
    record = result.one_or_none()
    if record is None:
        raise HTTPException(401, "Admin session expired")
    session, user = record
    now = int(time())
    if session.expires_at <= now or (session.access_expires_at <= now and not allow_refresh):
        raise HTTPException(401, "Admin session expired")
    return session, await get_admin_profile(db, user)


async def refresh_session(db: AsyncSession, token: str | None) -> AdminProfile:
    session, profile = await get_session(db, token, allow_refresh=True)
    now = int(time())
    updated = await db.execute(
        update(AdminSession)
        .where(
            AdminSession.token_digest == session.token_digest,
            AdminSession.expires_at > now,
        )
        .values(access_expires_at=min(now + ACCESS_MAX_AGE, session.expires_at))
    )
    if not updated.rowcount:
        raise HTTPException(401, "Admin session expired")
    await db.commit()
    return profile
