from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    IssueResponse,
    IssueCreate,
    DeleteResponse,
    CategoryListResponse,
    IssueUpdate,
    PaginatedIssueResponse,
)
from app.services.issue_service import (
    create_issue,
    get_my_issues,
    get_issue_by_id,
    delete_issue,
    fetch_categories,
    update_issue,
    get_all_issues,
    get_issues_by_location,
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


@router.get("/me", response_model=PaginatedIssueResponse, status_code=status.HTTP_200_OK)
async def my_issues(
    page: int = 1,
    limit: int = 10,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_my_issues(current_user.id, page, limit, db)


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_categories(db: AsyncSession = Depends(get_db)):
    return await fetch_categories(db)


@router.get(
    "/all", response_model=PaginatedIssueResponse, status_code=status.HTTP_200_OK
)
async def all_issues(
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    return await get_all_issues(page, limit, db)


@router.get(
    "/nearme",
    response_model=PaginatedIssueResponse,
    status_code=status.HTTP_200_OK,
)
async def issues_by_location(
    page: int = 1,
    limit: int = 10,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_issues_by_location(current_user.location_id, page, limit, db)


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


@router.patch(
    "/{issue_id}", response_model=IssueResponse, status_code=status.HTTP_200_OK
)
async def edit_issue(
    issue_id: str,
    category_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    images: list[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = IssueUpdate(
        category_id=category_id,
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        address=address,
    )
    return await update_issue(issue_id, current_user.id, data, db, images)
