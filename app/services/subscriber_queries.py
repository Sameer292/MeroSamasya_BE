from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import defer, selectinload

from app.models.models import Issue, User
from app.schemas.admin_subscribers import SubscriberDirectoryQuery, SubscriberPagination
from app.schemas.enum import AccountStatusEnum, IssueStatusEnum, UserRole
from app.services.subscriber_pagination import newest_first, page_rows, total_rows


def profile_options():
    return selectinload(User.location), defer(User.password, raiseload=True)


def matching_subscribers(query: SubscriberDirectoryQuery):
    subscribers = select(User.id, User.created_at).where(User.role == UserRole.citizen)
    if query.account_status == AccountStatusEnum.deleted:
        subscribers = subscribers.where(or_(
            User.account_status == AccountStatusEnum.deleted, User.deleted_at.is_not(None)
        ))
    elif query.account_status is not None:
        subscribers = subscribers.where(
            User.account_status == query.account_status, User.deleted_at.is_(None)
        )
    if search := (query.search or "").strip():
        subscribers = subscribers.where(or_(
            User.name.icontains(search, autoescape=True),
            User.email.icontains(search, autoescape=True),
            User.phone.icontains(search, autoescape=True),
        ))
    return subscribers.cte("matching_subscribers")


def reported_issues(subscriber_id):
    return Issue.citizen_id == subscriber_id, Issue.deleted_at.is_(None)


def issue_counts_for_page(page):
    return (
        select(
            Issue.citizen_id,
            func.count().label("reported_count"),
            resolved_count(Issue.status),
        )
        .join(page, Issue.citizen_id == page.c.id)
        .where(Issue.deleted_at.is_(None))
        .group_by(Issue.citizen_id)
        .subquery()
    )


def resolved_count(issue_status):
    return func.count().filter(issue_status == IssueStatusEnum.resolved).label("resolved_count")


def subscriber_directory(query: SubscriberDirectoryQuery):
    matching = matching_subscribers(query)
    total, page = total_rows(matching), page_rows(matching, query).cte("subscriber_page")
    counts = issue_counts_for_page(page)
    # Start from the totals so requests beyond the last page still return a count.
    return (
        select(
            User,
            func.coalesce(counts.c.reported_count, 0).label("reported_count"),
            func.coalesce(counts.c.resolved_count, 0).label("resolved_count"),
            total.c.total,
        )
        .select_from(total)
        .outerjoin(page, true())
        .outerjoin(User, User.id == page.c.id)
        .outerjoin(counts, counts.c.citizen_id == page.c.id)
        .options(*profile_options())
        .order_by(*newest_first(page.c))
    )


def subscriber_history(subscriber_id: str, pagination: SubscriberPagination):
    matching = (
        select(Issue.id, Issue.created_at, Issue.status)
        .where(*reported_issues(subscriber_id))
        .cte("matching_issues")
    )
    total = total_rows(matching, resolved_count(matching.c.status))
    page = page_rows(matching, pagination).subquery()
    return (
        select(Issue, total.c.total, total.c.resolved_count)
        .select_from(total)
        .outerjoin(page, true())
        .outerjoin(Issue, Issue.id == page.c.id)
        .options(selectinload(Issue.category), selectinload(Issue.media))
        .order_by(*newest_first(page.c))
    )
