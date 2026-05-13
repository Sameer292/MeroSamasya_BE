from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Issue, IssueMedia
from app.schemas.schema import IssueCreate
from fastapi import HTTPException, status, UploadFile
from app.core.cloudinary import upload_image
from app.schemas.enum import IssueStatusEnum

MAX_IMAGES = 3
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}


async def create_issue(
    data: IssueCreate,
    citizen_id: str,
    db: AsyncSession,
    images: list[UploadFile] = [],
):
    if len(images) > MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can upload a maximum of {MAX_IMAGES} images.",
        )

    for image in images:
        if image.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {image.content_type}. Allowed: jpeg, jpg, png, webp.",
            )

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
        await db.flush()

        for image in images:
            file_bytes = await image.read()
            url = await upload_image(file_bytes, citizen_id, issue.id)
            media = IssueMedia(issue_id=issue.id, url=url)
            db.add(media)

        await db.commit()

        result = await db.execute(
            select(Issue)
            .where(Issue.id == issue.id)
            .options(selectinload(Issue.media))
        )
        issue = result.scalar_one()
    except HTTPException:
        raise
    except Exception as e:
        print(e)
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
            .options(selectinload(Issue.media))
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
            select(Issue)
            .where(Issue.id == issue_id, Issue.deleted_at == None)
            .options(selectinload(Issue.media))
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


async def delete_issue(
    issue_id: str, citizen_id: str, delete_reason: str | None, db: AsyncSession
):
    issue = await get_issue_by_id(issue_id, db)

    if issue.citizen_id != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Failed to delete this issue.",
        )

    if issue.status != IssueStatusEnum.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue cannot be deleted.",
        )

    try:
        issue.deleted_at = datetime.now(timezone.utc)
        issue.delete_reason = delete_reason
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete issue.",
        )
    return {"message": "Issue deleted successfully."}