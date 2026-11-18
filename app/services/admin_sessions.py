from hashlib import sha256
from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_auth import AdminSession
from app.models.models import User


def digest_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


async def revoke_session(db: AsyncSession, token: str | None):
    if token:
        await db.execute(
            delete(AdminSession).where(AdminSession.token_digest == digest_token(token))
        )


async def create_session(db: AsyncSession, user: User, previous_token: str | None) -> str:
    await revoke_session(db, previous_token)
    token = token_urlsafe(32)
    db.add(AdminSession(token_digest=digest_token(token), user_id=user.id))
    await db.commit()
    return token


async def get_session_user(db: AsyncSession, token: str) -> User:
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
    return user
