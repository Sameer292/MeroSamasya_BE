import math
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.models import Issue, User, KycSubmission
from app.schemas.enum import IssueStatusEnum, KycStatusEnum
from app.services.issue_service import attach_votes
from app.services.kyc_service import serialize_kyc
from app.services.notification_service import notify

ALLOWED_TRANSITIONS = {
    IssueStatusEnum.open: {IssueStatusEnum.in_progress},
    IssueStatusEnum.in_progress: {IssueStatusEnum.resolved},
    IssueStatusEnum.resolved: {IssueStatusEnum.closed},
    IssueStatusEnum.closed: set(),
}

STATUS_LABELS = {
    IssueStatusEnum.open: "Open",
    IssueStatusEnum.in_progress: "In Progress",
    IssueStatusEnum.resolved: "Resolved",
    IssueStatusEnum.closed: "Closed",
}


async def admin_list_issues(
    page: int,
    limit: int,
    status_filter: IssueStatusEnum | None,
    category_id: str | None,
    db: AsyncSession,
):
    try:
        offset = (page - 1) * limit
        filters = [Issue.deleted_at.is_(None)]
        if status_filter is not None:
            filters.append(Issue.status == status_filter)
        if category_id is not None:
            filters.append(Issue.category_id == category_id)
        total = (
            await db.execute(select(func.count(Issue.id)).where(*filters))
        ).scalar() or 0
        result = await db.execute(
            select(Issue)
            .where(*filters)
            .options(
                selectinload(Issue.media),
                selectinload(Issue.category),
                selectinload(Issue.upvotes),
            )
            .order_by(Issue.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        issues = attach_votes(list(result.scalars().all()), None)
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
                "total_pages": math.ceil(total / limit) if limit else 0,
            },
            "issues": issues,
        },
    }


async def admin_update_status(
    issue_id: str, new_status: IssueStatusEnum, db: AsyncSession
):
    result = await db.execute(
        select(Issue)
        .where(Issue.id == issue_id, Issue.deleted_at.is_(None))
        .options(
            selectinload(Issue.media),
            selectinload(Issue.category),
            selectinload(Issue.upvotes),
        )
    )
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found."
        )
    if new_status != issue.status and new_status not in ALLOWED_TRANSITIONS[issue.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move issue from {issue.status.value} to {new_status.value}.",
        )
    try:
        issue.status = new_status
        if new_status == IssueStatusEnum.resolved:
            issue.resolved_at = datetime.now(timezone.utc)
        if issue.citizen_id:
            notify(
                db,
                issue.citizen_id,
                "status",
                "Status update",
                f"Your report '{issue.title}' is now {STATUS_LABELS[new_status]}.",
                issue_id=issue.id,
            )
        await db.commit()
        await db.refresh(issue)
        attach_votes([issue], None)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issue status.",
        )
    return {"message": "Issue status updated successfully", "data": issue}


async def admin_overview(db: AsyncSession):
    try:
        counts = {}
        for state in IssueStatusEnum:
            counts[state.value] = (
                await db.execute(
                    select(func.count(Issue.id)).where(
                        Issue.deleted_at.is_(None), Issue.status == state
                    )
                )
            ).scalar() or 0
        total_issues = (
            await db.execute(
                select(func.count(Issue.id)).where(Issue.deleted_at.is_(None))
            )
        ).scalar() or 0
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
            "open": counts["open"],
            "in_progress": counts["in_progress"],
            "resolved": counts["resolved"],
            "closed": counts["closed"],
            "total_issues": total_issues,
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
