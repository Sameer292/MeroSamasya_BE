from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    NotificationListResponse,
    NotificationResponse,
    ReadAllResponse,
)
from app.services.notification_service import (
    get_notifications,
    mark_read,
    mark_all_read,
    clear_all,
)
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


@router.get(
    "/", response_model=NotificationListResponse, status_code=status.HTTP_200_OK
)
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_notifications(current_user.id, page, limit, db)


@router.post(
    "/read-all", response_model=ReadAllResponse, status_code=status.HTTP_200_OK
)
async def read_all_notifications(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await mark_all_read(current_user.id, db)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
async def read_notification(
    notification_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await mark_read(notification_id, current_user.id, db)


@router.delete("/", status_code=status.HTTP_200_OK)
async def clear_notifications(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await clear_all(current_user.id, db)
