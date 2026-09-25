from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import User
from app.schemas.password_change import PasswordChangeRequest
from app.schemas.schema import (
    UserCreate,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    RegisterResponse,
    UserResponse,
)
from app.services.auth_service import (
    register_user,
    login_user,
)
from app.services.refresh_tokens import refresh_access_token, revoke_refresh_token
from app.services.password_change import change_password
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user
from app.services.location_service import serialize_user

router = APIRouter()


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await serialize_user(db, current_user, "User fetched successfully")


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    return await register_user(user, db)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    return await login_user(user, db)


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    return await refresh_access_token(request.refresh_token, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    await revoke_refresh_token(request.refresh_token, db)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_user_password(
    request: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await change_password(db, user, request)
