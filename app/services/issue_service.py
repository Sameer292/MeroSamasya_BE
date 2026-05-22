from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Issue, IssueMedia, Category, User
from app.schemas.schema import IssueCreate, IssueUpdate
from fastapi import HTTPException, status, UploadFile
from app.core.cloudinary import upload_image
from app.schemas.enum import IssueStatusEnum
import math

MAX_IMAGES = 3
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}


async def create_issue(
    data: IssueCreate,
    citizen_id: str,
    db: AsyncSession,
    images: list[UploadFile] = [],
):
    if len(images) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload at least 1 image.",
        )

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
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
            )
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

    return {
        "message": "Issue created successfully",
        "data": issue,
    }


async def get_my_issues(citizen_id: str, page: int, limit: int, db: AsyncSession):
    try:
        offset = (page - 1) * limit

        count_result = await db.execute(
            select(func.count(Issue.id)).where(
                Issue.citizen_id == citizen_id, Issue.deleted_at.is_(None)
            )
        )
        total = count_result.scalar()

        result = await db.execute(
            select(Issue)
            .where(Issue.citizen_id == citizen_id, Issue.deleted_at.is_(None))
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
            )
            .order_by(Issue.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        issues = result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issues.",
        )

    return {
        "message": "Issues fetched successfully",
        "data": {
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": math.ceil(total / limit),
            },
            "issues": issues,
        },
    }


async def get_issue_by_id(issue_id: str, db: AsyncSession):
    try:
        result = await db.execute(
            select(Issue)
            .where(Issue.id == issue_id, Issue.deleted_at.is_(None))
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
            )
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

    return {
        "message": "Issue fetched successfully",
        "data": issue,
    }


async def delete_issue(
    issue_id: str, citizen_id: str, delete_reason: str | None, db: AsyncSession
):
    issue_response = await get_issue_by_id(issue_id, db)
    issue = issue_response["data"]

    if issue.citizen_id != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this issue.",
        )

    if issue.status != IssueStatusEnum.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only open issues can be deleted.",
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

    return {"message": "Issue deleted successfully.", "data": {"id": issue_id}}


async def update_issue(
    issue_id: str,
    citizen_id: str,
    data: IssueUpdate,
    db: AsyncSession,
    images: list[UploadFile] = [],
):
    issue_response = await get_issue_by_id(issue_id, db)
    issue = issue_response["data"]

    if issue.citizen_id != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to edit this issue.",
        )

    if issue.status != IssueStatusEnum.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only open issues can be edited.",
        )

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
        if data.category_id is not None:
            issue.category_id = data.category_id
        if data.title is not None:
            issue.title = data.title
        if data.description is not None:
            issue.description = data.description
        if data.latitude is not None:
            issue.latitude = data.latitude
        if data.longitude is not None:
            issue.longitude = data.longitude
        if data.address is not None:
            issue.address = data.address

        if len(images) > 0:
            await db.execute(
                IssueMedia.__table__.delete().where(IssueMedia.issue_id == issue_id)
            )
            for image in images:
                file_bytes = await image.read()
                url = await upload_image(file_bytes, citizen_id, issue_id)
                media = IssueMedia(issue_id=issue_id, url=url)
                db.add(media)

        await db.commit()
        db.expire_all()

        result = await db.execute(
            select(Issue)
            .where(Issue.id == issue_id)
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
            )
        )
        updated_issue = result.scalar_one()
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issue. Please try again.",
        )

    return {
        "message": "Issue updated successfully",
        "data": updated_issue,
    }


async def get_all_issues(page: int, limit: int, db: AsyncSession):
    try:
        offset = (page - 1) * limit

        count_result = await db.execute(
            select(func.count(Issue.id)).where(Issue.deleted_at.is_(None))
        )
        total = count_result.scalar()
        print(f"Total issues: {total}")  # ← add this
        print(f"Offset: {offset}, Limit: {limit}")  # ← add this
        result = await db.execute(
            select(Issue)
            .where(Issue.deleted_at.is_(None))
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
            )
            .order_by(Issue.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        issues = result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issues.",
        )

    return {
        "message": "Issues fetched successfully",
        "data": {
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": math.ceil(total / limit),
            },
            "issues": issues,
        },
    }


async def get_issues_by_location(
    location_id: str | None, page: int, limit: int, db: AsyncSession
):
    if not location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no location set.",
        )
    try:
        offset = (page - 1) * limit

        count_result = await db.execute(
            select(func.count(Issue.id))
            .join(User, User.id == Issue.citizen_id)
            .where(Issue.deleted_at.is_(None), User.location_id == location_id)
        )
        total = count_result.scalar()

        result = await db.execute(
            select(Issue)
            .join(User, User.id == Issue.citizen_id)
            .where(Issue.deleted_at.is_(None), User.location_id == location_id)
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
            )
            .order_by(Issue.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        issues = result.scalars().all()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issues.",
        )

    return {
        "message": "Issues fetched successfully",
        "data": {
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": math.ceil(total / limit),
            },
            "issues": issues,
        },
    }
