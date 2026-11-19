from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.schemas.admin_subscribers import (
    SubscriberDirectoryQuery,
    SubscriberPagination,
    SubscriberProfile,
)
from app.schemas.enum import AccountStatusEnum, UserRole
from app.services.subscriber_pagination import pagination_meta
from app.services.subscriber_queries import profile_options, subscriber_directory, subscriber_history


def subscriber_data(user: User, reported_count: int, resolved_count: int):
    profile = SubscriberProfile.model_validate(user)
    if profile.deleted_at is not None:
        profile.account_status = AccountStatusEnum.deleted
    return profile.model_dump() | {
        "reported_count": reported_count,
        "resolved_count": resolved_count,
    }


async def list_subscribers(db: AsyncSession, query: SubscriberDirectoryQuery):
    rows = (await db.execute(subscriber_directory(query))).all()
    return {"data": {
        "meta": pagination_meta(query, rows[0].total),
        "subscribers": [
            subscriber_data(user, reported, resolved)
            for user, reported, resolved, _ in rows if user is not None
        ],
    }}


async def get_subscriber(db: AsyncSession, subscriber_id: str, pagination: SubscriberPagination):
    user = await db.scalar(
        select(User)
        .where(User.id == subscriber_id, User.role == UserRole.citizen)
        .options(*profile_options())
    )
    if user is None:
        raise HTTPException(404, "Subscriber not found")
    rows = (await db.execute(subscriber_history(subscriber_id, pagination))).all()
    _, total, resolved = rows[0]
    return {"data": subscriber_data(user, total, resolved) | {
        "issue_history": {
            "meta": pagination_meta(pagination, total),
            "issues": [issue for issue, _, _ in rows if issue is not None],
        },
    }}
