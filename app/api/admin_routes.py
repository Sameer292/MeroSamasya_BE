from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    IssueResponse,
    AdminOverviewResponse,
    KycListResponse,
    KycResponse,
    KycReviewRequest,
    StatusUpdateRequest,
)
from app.services.admin_service import (
    admin_update_status,
    admin_overview,
    admin_list_kyc,
    admin_review_kyc,
)
from app.core.database import get_db
from app.core.admin_config import NO_STORE
from app.dependencies.admin_deps import require_admin, require_admin_write
from app.models.models import User

router = APIRouter()


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
    admin: Annotated[User, Depends(require_admin_write)],
    db: AsyncSession = Depends(get_db),
):
    return await admin_update_status(issue_id, request.status, admin.id, db)


@router.get(
    "/kyc",
    response_model=KycListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_kyc(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    response.headers.update(NO_STORE)
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
    _admin=Depends(require_admin_write),
):
    return await admin_review_kyc(
        submission_id, request.status, request.note, db
    )
