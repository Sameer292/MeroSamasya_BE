from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    UserCreate,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    RegisterResponse,
    UserResponse,
    LocationResponse,
    UpdateLocationRequest,
)
from app.services.auth_service import (
    register_user,
    login_user,
    refresh_access_token,
    get_locations,
    update_user_location
)
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


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


@router.get(
    "/locations", response_model=list[LocationResponse], status_code=status.HTTP_200_OK
)
async def locations(db: AsyncSession = Depends(get_db)):
    return await get_locations(db)

@router.patch("/location", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_location(
    request: UpdateLocationRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_user_location(current_user, request.location_id, db)