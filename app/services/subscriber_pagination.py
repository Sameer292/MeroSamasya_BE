from sqlalchemy import func, select

from app.schemas.admin_subscribers import SubscriberPagination
from app.schemas.schema import PaginationMeta


def newest_first(columns):
    return columns.created_at.desc().nulls_last(), columns.id.desc()


def page_rows(matching, pagination: SubscriberPagination):
    return (
        select(matching)
        .order_by(*newest_first(matching.c))
        .offset((pagination.page - 1) * pagination.limit)
        .limit(pagination.limit)
    )


def total_rows(matching, *extra_counts):
    return select(func.count().label("total"), *extra_counts).select_from(matching).subquery()


def pagination_meta(pagination: SubscriberPagination, total: int) -> PaginationMeta:
    return PaginationMeta(
        page=pagination.page,
        limit=pagination.limit,
        total=total,
        total_pages=(total + pagination.limit - 1) // pagination.limit,
    )
