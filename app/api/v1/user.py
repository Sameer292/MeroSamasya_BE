from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.schema import UserResponse
from app.dependencies.auth import get_current_user
from app.core.database import db 

router = APIRouter()

@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(current_user=Depends(get_current_user)):
    try:
        user_id = current_user.id
        public_user = db.table("Users").select("*").eq("id", user_id).single().execute()

        if not public_user.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        user_data = public_user.data
        return {
            "id": user_id,
            "email": current_user.email,
            "first_name": user_data.get("first_name"),
            "middle_name": user_data.get("middle_name"),
            "last_name": user_data.get("last_name"),
            "phone": user_data.get("phone"),
            "role": user_data.get("role"),
            "profile_picture_url": user_data.get("profile_picture_url"),
            "account_status": user_data.get("account_status"),
            "created_at": user_data.get("created_at"),
            "updated_at": user_data.get("updated_at"),
            "deleted_at": user_data.get("deleted_at"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch user info")