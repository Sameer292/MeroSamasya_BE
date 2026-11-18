from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.models import User
from app.services.account_access import require_active_account
from app.services.jwt_tokens import get_token_subject

security = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(security)]


async def get_current_user(
    credentials: BearerCredentials, db: AsyncSession = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = get_token_subject(credentials.credentials)
    user = await db.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.location))
    )
    return require_active_account(user)
