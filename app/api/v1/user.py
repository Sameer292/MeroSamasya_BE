from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.schema import UserResponse
from app.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.models import User

router = APIRouter()

@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        user_id = current_user["sub"]
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch user info")