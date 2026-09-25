from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    PaginatedIssueResponse,
    IssueResponse,
    AdminOverviewResponse,
    KycListResponse,
    KycResponse,
    KycReviewRequest,
    StatusUpdateRequest,
)
from app.schemas.enum import IssueStatusEnum
from app.services.admin_service import (
    admin_list_issues,
    admin_update_status,
    admin_overview,
    admin_list_kyc,
    admin_review_kyc,
)
from app.core.database import get_db
from app.dependencies.admin_deps import require_admin

router = APIRouter()


@router.get(
    "/issues",
    response_model=PaginatedIssueResponse,
    status_code=status.HTTP_200_OK,
)
async def list_issues(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status_filter: Optional[IssueStatusEnum] = Query(None, alias="status"),
    category_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    return await admin_list_issues(page, limit, status_filter, category_id, db)


@router.get(
    "/issues/overview",
    response_model=AdminOverviewResponse,
    status_code=status.HTTP_200_OK,
)
async def overview(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    return await admin_overview(db)


@router.patch(
    "/issues/{issue_id}/status",
    response_model=IssueResponse,
    status_code=status.HTTP_200_OK,
)
async def update_issue_status(
    issue_id: str,
    request: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    return await admin_update_status(issue_id, request.status, db)


@router.get(
    "/kyc",
    response_model=KycListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_kyc(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    return await admin_list_kyc(page, limit, status_filter, db)


@router.patch(
    "/kyc/{submission_id}",
    response_model=KycResponse,
    status_code=status.HTTP_200_OK,
)
async def review_kyc(
    submission_id: str,
    request: KycReviewRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    return await admin_review_kyc(
        submission_id, request.status, request.note, db
    )
