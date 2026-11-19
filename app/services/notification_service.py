import math

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.models import Notification


def notify(
    db: AsyncSession,
    user_id: str,
    type: str,
    title: str,
    message: str,
    issue_id: str | None = None,
):
    """Queue a notification; committed by the caller's transaction."""
    db.add(
        Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            issue_id=issue_id,
        )
    )


async def get_notifications(
    user_id: str, page: int, limit: int, db: AsyncSession
):
    try:
        offset = (page - 1) * limit
        total = (
            await db.execute(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id
                )
            )
        ).scalar() or 0
        unread = (
            await db.execute(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.read.is_(False),
                )
            )
        ).scalar() or 0
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        notifications = result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notifications.",
        )
    return {
        "message": "Notifications fetched successfully",
        "data": {
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": math.ceil(total / limit) if limit else 0,
            },
            "unread_count": unread,
            "notifications": notifications,
        },
    }


async def mark_read(notification_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    try:
        notification.read = True
        await db.commit()
        await db.refresh(notification)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read.",
        )
    return {"message": "Notification marked as read", "data": notification}


async def clear_all(user_id: str, db: AsyncSession):
    try:
        result = await db.execute(
            select(Notification).where(Notification.user_id == user_id)
        )
        all_notifications = result.scalars().all()
        for notification in all_notifications:
            await db.delete(notification)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear notifications.",
        )
    return {"message": "Notifications cleared"}
