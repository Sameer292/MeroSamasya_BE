from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_config import ADMIN_COOKIE_NAME, ADMIN_WEB_ORIGIN
from app.core.database import get_db
from app.dependencies.auth_deps import BearerCredentials, get_current_user
from app.models.models import User
from app.schemas.enum import UserRole
from app.services.admin_sessions import get_session_user

AdminSessionCookie = Annotated[str | None, Cookie(alias=ADMIN_COOKIE_NAME)]
Database = Annotated[AsyncSession, Depends(get_db)]


def check_admin_role(user: User) -> None:
    if user.role not in (UserRole.admin, UserRole.superadmin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin permission required")


async def require_admin(
    credentials: BearerCredentials, db: Database, session: AdminSessionCookie = None
) -> User:
    if credentials is None and session:
        user = await get_session_user(db, session)
    else:
        user = await get_current_user(credentials, db)
    check_admin_role(user)
    return user


async def verify_admin_origin(request: Request) -> None:
    if request.headers.get("origin") != ADMIN_WEB_ORIGIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid origin")
