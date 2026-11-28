from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import selectinload

from app.models.models import Issue, Upvote, User
from app.schemas.admin_issues import AdminIssueQuery
from app.schemas.enum import IssueStatusEnum


def issue_read_options():
    return (
        selectinload(Issue.media),
        selectinload(Issue.category),
        selectinload(Issue.citizen).load_only(User.id, User.name),
    )


def filtered_issue_ids(query: AdminIssueQuery):
    issues = select(Issue.id, Issue.created_at).where(Issue.deleted_at.is_(None))
    if query.sort == "upvotes":
        votes = select(func.count()).where(Upvote.issue_id == Issue.id).scalar_subquery()
        issues = issues.add_columns(votes.label("vote_rank"))
    if query.south is not None:
        issues = issues.where(
            Issue.latitude.between(query.south, query.north),
            Issue.longitude.between(query.west, query.east),
        )
    if query.status is not None:
        issues = issues.where(Issue.status == query.status)
    if query.active_only:
        issues = issues.where(Issue.status.in_((IssueStatusEnum.open, IssueStatusEnum.in_progress)))
    if query.category_id is not None:
        issues = issues.where(Issue.category_id == query.category_id)
    if search := (query.search or "").strip():
        issues = issues.where(or_(
            Issue.title.icontains(search, autoescape=True),
            Issue.description.icontains(search, autoescape=True),
            Issue.address.icontains(search, autoescape=True),
        ))
    return issues


def issue_order(columns, query: AdminIssueQuery):
    if query.sort == "oldest":
        return columns.created_at.asc().nulls_last(), columns.id.asc()
    newest = columns.created_at.desc().nulls_last(), columns.id.desc()
    if query.sort == "upvotes":
        return columns.vote_rank.desc().nulls_last(), *newest
    return newest


def admin_issue_page(query: AdminIssueQuery):
    matching = filtered_issue_ids(query).cte("matching_issues")
    total = select(func.count().label("total")).select_from(matching).subquery()
    page = (
        select(matching)
        .order_by(*issue_order(matching.c, query))
        .offset((query.page - 1) * query.limit)
        .limit(query.limit)
        .subquery()
    )
    # Keep the total available even when the requested page has no rows.
    return (
        select(Issue, total.c.total)
        .select_from(total)
        .outerjoin(page, true())
        .outerjoin(Issue, Issue.id == page.c.id)
        .options(*issue_read_options())
        .order_by(*issue_order(page.c, query))
    )
