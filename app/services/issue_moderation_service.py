from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.issue_moderation import IssueModerationEvent
from app.models.models import Category, Issue
from app.schemas.issue_moderation import (
    IssueModerationRequest,
    IssueModerationResult,
    ModeratedIssue,
    ModerationEvent,
)
from app.services.issue_transitions import resolution_timestamp


async def lock_issue(db: AsyncSession, issue_id: str) -> Issue:
    issue = await db.scalar(
        select(Issue)
        .where(Issue.id == issue_id, Issue.deleted_at.is_(None))
        .with_for_update()
    )
    if issue is None:
        raise HTTPException(404, "Issue not found")
    return issue


async def validate_category(db: AsyncSession, category_id: str) -> None:
    category = await db.scalar(
        select(Category.id)
        .where(Category.id == category_id, Category.deleted_at.is_(None))
        .with_for_update(read=True)
    )
    if category is None:
        raise HTTPException(422, "Category does not exist or is inactive")


def apply_moderation(issue: Issue, request: IssueModerationRequest, now: datetime):
    previous = ModeratedIssue.model_validate(issue).model_dump(mode="json")
    status = request.status or issue.status
    issue.resolved_at = resolution_timestamp(issue.status, status, issue.resolved_at, now)
    issue.status = status
    if request.category_id is not None:
        issue.category_id = request.category_id
    current = ModeratedIssue.model_validate(issue).model_dump(mode="json")
    return [
        {"field": field, "previous": previous[field], "current": current[field]}
        for field in ("category_id", "status", "resolved_at")
        if previous[field] != current[field]
    ]


async def moderate_issue(
    db: AsyncSession, issue_id: str, reviewer_id: str, request: IssueModerationRequest
) -> IssueModerationResult:
    issue = await lock_issue(db, issue_id)
    if request.category_id is not None and request.category_id != issue.category_id:
        await validate_category(db, request.category_id)
    now = datetime.now(timezone.utc)
    changes = apply_moderation(issue, request, now)
    event = None
    if changes:
        issue.updated_at = now
        event = IssueModerationEvent(
            issue_id=issue_id, reviewer_id=reviewer_id, created_at=now, changes=changes
        )
        db.add(event)
        await db.flush()
    result = IssueModerationResult(
        issue=ModeratedIssue.model_validate(issue),
        event=ModerationEvent.model_validate(event) if event else None,
    )
    await db.commit()
    return result


async def list_moderation_events(db: AsyncSession, issue_id: str):
    if await db.scalar(select(Issue.id).where(Issue.id == issue_id)) is None:
        raise HTTPException(404, "Issue not found")
    events = await db.scalars(
        select(IssueModerationEvent)
        .where(IssueModerationEvent.issue_id == issue_id)
        .order_by(IssueModerationEvent.created_at.desc(), IssueModerationEvent.id.desc())
    )
    return events.all()
