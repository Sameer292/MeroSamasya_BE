from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import UserCreate, UserLogin, TokenResponse, RefreshTokenRequest, RegisterResponse
from app.services.auth_service import register_user, login_user, refresh_access_token
from app.core.database import get_db

router = APIRouter()

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await register_user(user, db)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return result

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await login_user(user, db)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result["error"])
    return result

@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh(request: RefreshTokenRequest):
    result = await refresh_access_token(request.refresh_token)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result["error"])
    return result