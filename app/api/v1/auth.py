from fastapi import APIRouter, HTTPException, status
from app.schemas.schema import UserCreate, UserLogin, TokenResponse, RefreshTokenRequest, RegisterResponse
from app.services.auth_service import register_user, login_user, refresh_access_token

router = APIRouter()

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    result = await register_user(user)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin):
    result = await login_user(user)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return {
         "access_token": result["access_token"],
         "refresh_token": result["refresh_token"],
         "token_type": "bearer",
         "user_id": result["user_id"]
    }

@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshTokenRequest):
    result = await refresh_access_token(request.refresh_token)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result
