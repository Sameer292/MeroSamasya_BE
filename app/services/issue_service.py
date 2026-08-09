from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Issue, IssueMedia, Category, User, Upvote  
from app.schemas.schema import IssueCreate, IssueUpdate
from fastapi import HTTPException, status, UploadFile
from app.core.cloudinary import upload_image
from app.schemas.enum import IssueStatusEnum
import math

MAX_IMAGES = 3
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}


# ── Helper ────────────────────────────────────────────────────────────────────
async def attach_upvotes(issues: list, current_user_id: str | None, db: AsyncSession):
    result = []
    for issue in issues:
        issue.vote_count = len(issue.upvotes)                                    # ← .votes → .upvotes
        issue.has_voted = (
            any(v.user_id == current_user_id for v in issue.upvotes)             # ← .votes → .upvotes
            if current_user_id else False
        )
        result.append(issue)
    return result


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
                selectinload(Issue.upvotes),                                     # ← .votes → .upvotes
            )
        )
        issue = result.scalar_one()
        issue.vote_count = 0
        issue.has_voted = False

    except HTTPException:
        raise
    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issue. Please try again.",
        )

    return {"message": "Issue created successfully", "data": issue}


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
                selectinload(Issue.upvotes),                                     # ← .votes → .upvotes
            )
            .order_by(Issue.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        issues = result.scalars().all()
        issues = await attach_upvotes(issues, citizen_id, db)                   # ← attach_votes → attach_upvotes

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


async def get_issue_by_id(issue_id: str, db: AsyncSession, current_user_id: str | None = None):
    try:
        result = await db.execute(
            select(Issue)
            .where(Issue.id == issue_id, Issue.deleted_at.is_(None))
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
                selectinload(Issue.upvotes),                                     # ← .votes → .upvotes
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

    issue.vote_count = len(issue.upvotes)                                        # ← .votes → .upvotes
    issue.has_voted = (
        any(v.user_id == current_user_id for v in issue.upvotes)                 # ← .votes → .upvotes
        if current_user_id else False
    )

    return {"message": "Issue fetched successfully", "data": issue}


async def delete_issue(
    issue_id: str, citizen_id: str, delete_reason: str | None, db: AsyncSession
):
    issue_response = await get_issue_by_id(issue_id, db, citizen_id)
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


async def fetch_categories(db: AsyncSession):
    try:
        result = await db.execute(select(Category).where(Category.deleted_at.is_(None)))
        categories = result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch categories.",
        )

    return {"message": "Categories fetched successfully", "data": categories}


async def update_issue(
    issue_id: str,
    citizen_id: str,
    data: IssueUpdate,
    db: AsyncSession,
    images: list[UploadFile] = [],
):
    issue_response = await get_issue_by_id(issue_id, db, citizen_id)
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
                selectinload(Issue.upvotes),                                     # ← .votes → .upvotes
            )
        )
        updated_issue = result.scalar_one()
        updated_issue.vote_count = len(updated_issue.upvotes)                   # ← .votes → .upvotes
        updated_issue.has_voted = any(
            v.user_id == citizen_id for v in updated_issue.upvotes              # ← .votes → .upvotes
        )

    except HTTPException:
        raise
    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issue. Please try again.",
        )

    return {"message": "Issue updated successfully", "data": updated_issue}


async def get_all_issues(page: int, limit: int, db: AsyncSession, current_user_id: str | None = None):
    try:
        offset = (page - 1) * limit

        count_result = await db.execute(
            select(func.count(Issue.id)).where(Issue.deleted_at.is_(None))
        )
        total = count_result.scalar()

        result = await db.execute(
            select(Issue)
            .where(Issue.deleted_at.is_(None))
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
                selectinload(Issue.upvotes),                                     # ← .votes → .upvotes
            )
            .order_by(Issue.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        issues = result.scalars().all()
        issues = await attach_upvotes(issues, current_user_id, db)              # ← attach_votes → attach_upvotes

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
    location_id: str | None, page: int, limit: int, db: AsyncSession, current_user_id: str | None = None
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
                selectinload(Issue.upvotes),                                     # ← .votes → .upvotes
            )
            .order_by(Issue.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        issues = result.scalars().all()
        issues = await attach_upvotes(issues, current_user_id, db)              # ← attach_votes → attach_upvotes

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


async def toggle_vote(issue_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.deleted_at.is_(None)
        )
    )
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")

    vote_result = await db.execute(
        select(Upvote).where(                                                    # ← Vote → Upvote
            Upvote.issue_id == issue_id,                                         # ← Vote → Upvote
            Upvote.user_id == user_id,                                           # ← Vote → Upvote
        )
    )
    existing_vote = vote_result.scalar_one_or_none()

    try:
        if existing_vote:
            await db.delete(existing_vote)
            await db.commit()
            voted = False
            message = "Upvote removed successfully"                             # ← message updated
        else:
            db.add(Upvote(user_id=user_id, issue_id=issue_id))                  # ← Vote → Upvote
            await db.commit()
            voted = True
            message = "Upvoted successfully"                                    # ← message updated
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process upvote."
        )

    count_result = await db.execute(
        select(func.count(Upvote.id)).where(Upvote.issue_id == issue_id)        # ← Vote → Upvote
    )

    return {
        "message": message,
        "vote_count": count_result.scalar() or 0,
        "has_voted": voted,
    }