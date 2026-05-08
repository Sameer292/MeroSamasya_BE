from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import IssueCreate, IssueResponse, IssueListResponse
from app.services.issue_service import (
    create_issue,
    get_my_issues,
    get_issue_by_id,
    delete_issue,
)
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user
from typing import Optional

router = APIRouter()


@router.post("", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
async def open_issue(
    data: IssueCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_issue(data, current_user.id, db)


@router.get("/me", response_model=IssueListResponse, status_code=status.HTTP_200_OK)
async def my_issues(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_my_issues(current_user.id, db)


@router.get("/{issue_id}", response_model=IssueResponse, status_code=status.HTTP_200_OK)
async def issue_detail(
    issue_id: str,
    db: AsyncSession = Depends(get_db),
):
    return await get_issue_by_id(issue_id, db)


@router.delete("/{issue_id}", status_code=status.HTTP_200_OK)
async def remove_issue(
    issue_id: str,
    delete_reason: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await delete_issue(issue_id, current_user.id, delete_reason, db)