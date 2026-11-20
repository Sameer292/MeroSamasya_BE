import math

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.models import User, KycSubmission
from app.schemas.enum import IssueStatusEnum, KycStatusEnum
from app.schemas.issue_moderation import IssueModerationRequest
from app.services.admin_issue_service import get_issue_status_totals
from app.services.issue_moderation_service import moderate_issue
from app.services.issue_service import get_issue_by_id
from app.services.kyc_service import serialize_kyc
from app.services.notification_service import notify

async def admin_update_status(
    issue_id: str, new_status: IssueStatusEnum, reviewer_id: str, db: AsyncSession
):
    await moderate_issue(db, issue_id, reviewer_id, IssueModerationRequest(status=new_status))
    issue = await get_issue_by_id(issue_id, db)
    return {"message": "Issue status updated successfully", "data": issue["data"]}


async def admin_overview(db: AsyncSession):
    try:
        counts = (await get_issue_status_totals(db)).model_dump()
        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
        kyc_pending = (
            await db.execute(
                select(func.count(KycSubmission.id)).where(
                    KycSubmission.status == KycStatusEnum.pending
                )
            )
        ).scalar() or 0
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch overview.",
        )
    return {
        "message": "Overview fetched successfully",
        "data": {
            **counts,
            "total_issues": sum(counts.values()),
            "total_users": total_users,
            "kyc_pending": kyc_pending,
        },
    }


async def admin_list_kyc(
    page: int,
    limit: int,
    status_filter: str | None,
    db: AsyncSession,
):
    try:
        offset = (page - 1) * limit
        filters = []
        if status_filter is not None:
            if status_filter not in ("pending", "approved", "rejected"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status filter.",
                )
            filters.append(KycSubmission.status == status_filter)
        total = (
            await db.execute(select(func.count(KycSubmission.id)).where(*filters))
        ).scalar() or 0
        result = await db.execute(
            select(KycSubmission)
            .where(*filters)
            .order_by(KycSubmission.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        submissions = result.scalars().all()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch KYC submissions.",
        )
    return {
        "message": "KYC submissions fetched successfully",
        "data": {
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": math.ceil(total / limit) if limit else 0,
            },
            "submissions": [serialize_kyc(s) for s in submissions],
        },
    }


async def admin_review_kyc(
    submission_id: str, new_status: str, note: str | None, db: AsyncSession
):
    result = await db.execute(
        select(KycSubmission).where(KycSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="KYC submission not found."
        )
    try:
        submission.status = KycStatusEnum(new_status)
        submission.reviewer_note = note
        notify(
            db,
            submission.user_id,
            "kyc",
            "KYC " + ("approved" if new_status == "approved" else "rejected"),
            (
                "Your identity verification was approved."
                if new_status == "approved"
                else f"Your identity verification was rejected.{(' Reason: ' + note) if note else ''}"
            ),
        )
        await db.commit()
        await db.refresh(submission)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to review KYC submission.",
        )
    return {
        "message": "KYC reviewed successfully",
        "data": serialize_kyc(submission),
    }
