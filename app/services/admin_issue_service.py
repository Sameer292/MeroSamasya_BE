from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Issue
from app.schemas.admin_issues import AdminIssueQuery, AdminIssueStatusTotals
from app.services.admin_issue_queries import admin_issue_page, issue_read_options


async def get_issue_status_totals(db: AsyncSession) -> AdminIssueStatusTotals:
    result = await db.execute(
        select(Issue.status, func.count())
        .where(Issue.deleted_at.is_(None))
        .group_by(Issue.status)
    )
    return AdminIssueStatusTotals(**{status.value: count for status, count in result})


async def list_admin_issues(db: AsyncSession, query: AdminIssueQuery):
    rows = (await db.execute(admin_issue_page(query))).all()
    total = rows[0].total
    return {
        "message": "Issues fetched successfully",
        "data": {
            "meta": {
                "total": total,
                "page": query.page,
                "limit": query.limit,
                "total_pages": (total + query.limit - 1) // query.limit,
            },
            "issues": [issue for issue, _ in rows if issue is not None],
        },
    }


async def get_admin_issue(db: AsyncSession, issue_id: str):
    issue = await db.scalar(
        select(Issue)
        .where(Issue.id == issue_id, Issue.deleted_at.is_(None))
        .options(*issue_read_options())
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found.")
    return {"message": "Issue fetched successfully", "data": issue}
