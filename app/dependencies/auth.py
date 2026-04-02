from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from app.services.auth_service import get_user_from_token

security = HTTPBearer()

async def get_current_user(credentials=Depends(security)):
    token = credentials.credentials
    user = await get_user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user