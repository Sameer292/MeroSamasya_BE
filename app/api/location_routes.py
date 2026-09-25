from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import UpdateLocationRequest, UserResponse
from app.services.location_service import update_user_location
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


@router.patch("/location", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_location(
    request: UpdateLocationRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_user_location(current_user, request.location_id, db)
