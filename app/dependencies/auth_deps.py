from time import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import User
from app.models.refresh_token import RefreshToken
from app.services.account_access import require_active_account
from app.services.jwt_tokens import get_token_session

security = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(security)]


async def get_current_user(
    credentials: BearerCredentials, db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id, session_id = get_token_session(credentials.credentials)
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session refresh required")
    user = await db.scalar(
        select(User)
        .join(RefreshToken, RefreshToken.user_id == User.id)
        .where(
            User.id == user_id,
            RefreshToken.session_id == session_id,
            RefreshToken.expires_at > int(time()),
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session revoked")
    return require_active_account(user)
