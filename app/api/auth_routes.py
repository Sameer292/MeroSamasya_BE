from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    UserCreate,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    RegisterResponse,
)
from app.services.auth_service import (
    register_user,
    login_user,
    refresh_access_token,
)
from app.core.database import get_db

router = APIRouter()


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    return await register_user(user, db)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    return await login_user(user, db)


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh(request: RefreshTokenRequest):
    return await refresh_access_token(request.refresh_token)
