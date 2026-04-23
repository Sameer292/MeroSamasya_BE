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
        result = await db.execute(select(User).where(User.id == current_user.id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User profile not found")

        return {
            "id": user.id,
            "email": current_user.email,
            "first_name": user.first_name,
            "middle_name": user.middle_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role,
            "profile_picture_url": user.profile_picture_url,
            "account_status": user.account_status,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "deleted_at": user.deleted_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch user info")