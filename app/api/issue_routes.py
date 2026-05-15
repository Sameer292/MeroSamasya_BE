from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    IssueResponse,
    IssueListResponse,
    IssueCreate,
    DeleteResponse,
)
from app.services.issue_service import (
    create_issue,
    get_my_issues,
    get_issue_by_id,
    delete_issue,
)
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


@router.post(
    "/create", response_model=IssueResponse, status_code=status.HTTP_201_CREATED
)
async def open_issue(
    category_id: str = Form(...),
    title: str = Form(..., min_length=3, max_length=200),
    description: Optional[str] = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: Optional[str] = Form(None),
    images: list[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    data = IssueCreate(
        category_id=category_id,
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        address=address,
    )
    return await create_issue(data, current_user.id, db, images)


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


@router.delete(
    "/{issue_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK
)
async def remove_issue(
    issue_id: str,
    delete_reason: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await delete_issue(issue_id, current_user.id, delete_reason, db)
