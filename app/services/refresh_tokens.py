from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.models.refresh_token import RefreshToken
from app.schemas.schema import TokenData
from app.services.account_access import require_active_account
from app.services.jwt_tokens import REFRESH_LIFETIME, create_token, get_token_session
from app.services.token_digest import digest_token


def new_token_pair(user_id: str, session_id: str, now: datetime) -> TokenData:
    return TokenData(
        access_token=create_token(user_id, session_id, now=now),
        refresh_token=create_token(user_id, session_id, refresh=True, now=now),
        user_id=user_id,
    )


async def issue_token_pair(db: AsyncSession, user_id: str) -> TokenData:
    now = datetime.now(UTC)
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.expires_at <= int(now.timestamp()),
        )
    )
    session_id = str(uuid4())
    tokens = new_token_pair(user_id, session_id, now)
    db.add(
        RefreshToken(
            token_digest=digest_token(tokens.refresh_token),
            session_id=session_id,
            user_id=user_id,
            expires_at=int((now + REFRESH_LIFETIME).timestamp()),
        )
    )
    await db.commit()
    return tokens


async def refresh_access_token(token: str, db: AsyncSession):
    user_id, session_id = get_token_session(token, refresh=True)
    require_active_account(await db.get(User, user_id, with_for_update=True))
    now = datetime.now(UTC)
    token_digest = digest_token(token)
    session_id = session_id or token_digest
    tokens = new_token_pair(user_id, session_id, now)
    rotated = await db.scalar(
        update(RefreshToken)
        .where(
            RefreshToken.token_digest == token_digest,
            RefreshToken.user_id == user_id,
            RefreshToken.expires_at > int(now.timestamp()),
        )
        .values(
            token_digest=digest_token(tokens.refresh_token),
            session_id=session_id,
            expires_at=int((now + REFRESH_LIFETIME).timestamp()),
        )
        .returning(RefreshToken.token_digest)
    )
    if rotated is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")
    await db.commit()
    return {"message": "Token refreshed successfully", "data": tokens}


async def revoke_refresh_token(token: str, db: AsyncSession) -> None:
    # An older signed refresh token can still revoke its session after rotation.
    user_id, session_id = get_token_session(token, refresh=True, allow_expired=True)
    if session_id is None:
        token_digest = digest_token(token)
        session_match = or_(
            RefreshToken.session_id == token_digest,
            RefreshToken.token_digest == token_digest,
        )
    else:
        session_match = RefreshToken.session_id == session_id
    await db.execute(
        delete(RefreshToken).where(RefreshToken.user_id == user_id, session_match)
    )
    await db.commit()
