from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies.admin_deps import Database, require_admin
from app.schemas.admin_subscribers import (
    SubscriberDetailResponse,
    SubscriberDirectoryQuery,
    SubscriberDirectoryResponse,
    SubscriberPagination,
)
from app.services.subscriber_service import get_subscriber, list_subscribers


def prevent_profile_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(dependencies=[Depends(require_admin), Depends(prevent_profile_caching)])


@router.get("", response_model=SubscriberDirectoryResponse)
async def subscriber_directory(db: Database, query: Annotated[SubscriberDirectoryQuery, Query()]):
    return await list_subscribers(db, query)


@router.get("/{subscriber_id}", response_model=SubscriberDetailResponse)
async def subscriber_detail(
    subscriber_id: str, db: Database, pagination: Annotated[SubscriberPagination, Query()]
):
    return await get_subscriber(db, subscriber_id, pagination)
