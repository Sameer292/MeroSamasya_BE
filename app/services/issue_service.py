from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Issue
from app.schemas.schema import IssueCreate
from fastapi import HTTPException, status


async def create_issue(data: IssueCreate, citizen_id: str, db: AsyncSession):
    try:
        issue = Issue(
            citizen_id=citizen_id,
            category_id=data.category_id,
            title=data.title,
            description=data.description,
            latitude=data.latitude,
            longitude=data.longitude,
            address=data.address,
        )
        db.add(issue)
        await db.commit()
        await db.refresh(issue)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issue. Please try again.",
        )
    return issue


async def get_my_issues(citizen_id: str, db: AsyncSession):
    try:
        result = await db.execute(
            select(Issue)
            .where(Issue.citizen_id == citizen_id, Issue.deleted_at == None)
            .order_by(Issue.created_at.desc())
        )
        issues = result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issues.",
        )
    return {"total": len(issues), "issues": issues}


async def get_issue_by_id(issue_id: str, db: AsyncSession):
    try:
        result = await db.execute(
            select(Issue).where(Issue.id == issue_id, Issue.deleted_at == None)
        )
        issue = result.scalar_one_or_none()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issue.",
        )
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found.",
        )
    return issue


async def delete_issue(issue_id: str, citizen_id: str, delete_reason: str | None, db: AsyncSession):
    issue = await get_issue_by_id(issue_id, db)

    if issue.citizen_id != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this issue.",
        )
    try:
        issue.deleted_at = datetime.utcnow()
        issue.delete_reason = delete_reason
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete issue.",
        )
    return {"message": "Issue deleted successfully."}