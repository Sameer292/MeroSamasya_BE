from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.models import User
from app.services.auth_service import decode_token
import jwt

security = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(security)]


def get_access_token_subject(token: str) -> str:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    subject = payload.get("sub")
    if payload.get("refresh") or not isinstance(subject, str) or not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return subject


async def get_current_user(
    credentials: BearerCredentials, db: AsyncSession = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = get_access_token_subject(credentials.credentials)
    user = await db.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.location))
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
