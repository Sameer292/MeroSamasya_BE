from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.models.refresh_token import RefreshToken
from app.schemas.schema import TokenData
from app.services.account_access import require_active_account
from app.services.jwt_tokens import REFRESH_LIFETIME, create_token, get_token_subject
from app.services.token_digest import digest_token


async def issue_token_pair(db: AsyncSession, user_id: str) -> TokenData:
    now = datetime.now(timezone.utc)
    await db.execute(delete(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.expires_at <= int(now.timestamp()),
    ))
    refresh_token = create_token(user_id, refresh=True, now=now)
    db.add(RefreshToken(
        token_digest=digest_token(refresh_token),
        user_id=user_id,
        expires_at=int((now + REFRESH_LIFETIME).timestamp()),
    ))
    tokens = TokenData(
        access_token=create_token(user_id), refresh_token=refresh_token, user_id=user_id
    )
    await db.commit()
    return tokens


async def delete_refresh_token(db: AsyncSession, token: str, user_id: str) -> bool:
    deleted = await db.scalar(
        delete(RefreshToken)
        .where(
            RefreshToken.token_digest == digest_token(token),
            RefreshToken.user_id == user_id,
        )
        .returning(RefreshToken.token_digest)
    )
    return deleted is not None


async def refresh_access_token(token: str, db: AsyncSession):
    user_id = get_token_subject(token, refresh=True)
    require_active_account(await db.get(User, user_id))
    if not await delete_refresh_token(db, token, user_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")
    return {
        "message": "Token refreshed successfully",
        "data": await issue_token_pair(db, user_id),
    }


async def revoke_refresh_token(token: str, db: AsyncSession) -> None:
    user_id = get_token_subject(token, refresh=True)
    await delete_refresh_token(db, token, user_id)
    await db.commit()
