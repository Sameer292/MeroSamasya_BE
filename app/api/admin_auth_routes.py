from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.admin_config import ADMIN_COOKIE_NAME, ADMIN_COOKIE_SECURE, NO_STORE
from app.dependencies.admin_deps import (
    AdminSessionCookie,
    Database,
    check_admin_role,
    require_admin,
    verify_admin_origin,
)
from app.models.models import User
from app.schemas.admin_auth import AdminProfileResponse
from app.schemas.schema import UserLogin
from app.services.admin_sessions import create_session, revoke_session
from app.services.auth_service import authenticate_user

router = APIRouter()
COOKIE_OPTIONS = {"secure": ADMIN_COOKIE_SECURE, "httponly": True, "samesite": "lax"}


@router.post("/login", status_code=204, dependencies=[Depends(verify_admin_origin)])
async def login_admin(
    credentials: UserLogin, db: Database, session: AdminSessionCookie = None
):
    user = await authenticate_user(credentials, db)
    check_admin_role(user)
    token = await create_session(db, user, session)
    response = Response(status_code=204, headers=NO_STORE)
    response.set_cookie(ADMIN_COOKIE_NAME, token, **COOKIE_OPTIONS)
    return response


@router.get("/me", response_model=AdminProfileResponse)
async def get_admin(response: Response, user: Annotated[User, Depends(require_admin)]):
    response.headers.update(NO_STORE)
    return {"data": {"email": user.email, "name": user.name, "role": user.role}}


@router.post(
    "/logout", status_code=204,
    dependencies=[Depends(require_admin), Depends(verify_admin_origin)],
)
async def logout_admin(db: Database, session: AdminSessionCookie = None):
    await revoke_session(db, session)
    await db.commit()
    response = Response(status_code=204, headers=NO_STORE)
    response.delete_cookie(ADMIN_COOKIE_NAME, **COOKIE_OPTIONS)
    return response
