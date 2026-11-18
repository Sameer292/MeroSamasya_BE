from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_config import ADMIN_COOKIE_NAME, ADMIN_COOKIE_SECURE, ADMIN_WEB_ORIGIN
from app.core.database import get_db
from app.schemas.admin_auth import AdminProfileResponse
from app.schemas.schema import UserLogin
from app.services.admin_sessions import (
    SESSION_MAX_AGE,
    create_session,
    get_session,
    refresh_session,
    revoke_session,
)
from app.services.auth_service import authenticate_user

router = APIRouter()
SessionCookie = Annotated[str | None, Cookie(alias=ADMIN_COOKIE_NAME)]
Database = Annotated[AsyncSession, Depends(get_db)]
COOKIE_OPTIONS = {"secure": ADMIN_COOKIE_SECURE, "httponly": True, "samesite": "lax"}
NO_STORE = {"Cache-Control": "private, no-store"}


async def verify_origin(request: Request):
    if request.headers.get("origin") != ADMIN_WEB_ORIGIN:
        raise HTTPException(403, "Invalid origin")


@router.post("/login", status_code=204, dependencies=[Depends(verify_origin)])
async def login_admin(credentials: UserLogin, db: Database, session: SessionCookie = None):
    user = await authenticate_user(credentials, db)
    token = await create_session(db, user, session)
    response = Response(status_code=204, headers=NO_STORE)
    response.set_cookie(ADMIN_COOKIE_NAME, token, max_age=SESSION_MAX_AGE, **COOKIE_OPTIONS)
    return response


@router.get("/me", response_model=AdminProfileResponse)
async def get_admin(response: Response, db: Database, session: SessionCookie = None):
    _, profile = await get_session(db, session)
    response.headers.update(NO_STORE)
    return {"data": profile}


@router.post("/refresh", response_model=AdminProfileResponse, dependencies=[Depends(verify_origin)])
async def refresh_admin(response: Response, db: Database, session: SessionCookie = None):
    profile = await refresh_session(db, session)
    response.headers.update(NO_STORE)
    return {"data": profile}


@router.post("/logout", status_code=204, dependencies=[Depends(verify_origin)])
async def logout_admin(db: Database, session: SessionCookie = None):
    await revoke_session(db, session)
    await db.commit()
    response = Response(status_code=204, headers=NO_STORE)
    response.delete_cookie(ADMIN_COOKIE_NAME, **COOKIE_OPTIONS)
    return response
