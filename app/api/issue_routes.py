from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
    UploadFile,
    File,
    Form,
)
from fastapi.exceptions import RequestValidationError
from typing import Annotated, Optional
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    IssueResponse,
    IssueCreate,
    IssueTitle,
    DeleteResponse,
    IssueUpdate,
    PaginatedIssueResponse,
    CategoryListResponse,
    UpvoteResponse,
)
from app.services.issue_service import (
    create_issue,
    get_my_issues,
    get_issue_by_id,
    delete_issue,
    update_issue,
    get_all_issues,
    get_issues_by_location,
    toggle_vote,
)
from app.services.category_service import get_categories
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


@router.post(
    "/create", response_model=IssueResponse, status_code=status.HTTP_201_CREATED
)
async def open_issue(
    title: Annotated[IssueTitle, Form()],
    category_id: str = Form(...),
    description: Optional[str] = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: Optional[str] = Form(None),
    local_level_id: str = Form(...),
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
        local_level_id=local_level_id,
    )
    return await create_issue(data, current_user.id, db, images)


@router.get(
    "/me", response_model=PaginatedIssueResponse, status_code=status.HTTP_200_OK
)
async def my_issues(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_my_issues(current_user.id, page, limit, db)


@router.get(
    "/categories", response_model=CategoryListResponse, status_code=status.HTTP_200_OK
)
async def issue_categories(db: AsyncSession = Depends(get_db)):
    # ponytail: alias the mobile client actually calls (GET /api/issues/categories)
    return await get_categories(db)


@router.get(
    "/all", response_model=PaginatedIssueResponse, status_code=status.HTTP_200_OK
)
async def all_issues(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_all_issues(page, limit, db, current_user.id)


@router.get(
    "/nearme",
    response_model=PaginatedIssueResponse,
    status_code=status.HTTP_200_OK,
)
async def issues_by_location(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_issues_by_location(
        current_user.location_id, page, limit, db, current_user.id
    )


@router.get("/{issue_id}", response_model=IssueResponse, status_code=status.HTTP_200_OK)
async def issue_detail(
    issue_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_issue_by_id(issue_id, db, current_user.id)


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
    request: Request,
    category_id: Optional[str] = Form(None),
    title: Annotated[IssueTitle | None, Form()] = None,
    description: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    local_level_id: Optional[str] = Form(None),
    retained_media_ids: Optional[str] = Form(None),
    images: list[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # FastAPI treats an empty form string as missing, but only omission should skip an edit.
    if title is None and "title" in await request.form():
        raise RequestValidationError([
            {"type": "value_error", "loc": ("body", "title"), "msg": "Title cannot be empty"}
        ])
    data = IssueUpdate(
        category_id=category_id,
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        address=address,
        local_level_id=local_level_id,
    )
    retained: list[str] | None = None
    if retained_media_ids is not None:
        try:
            parsed = json.loads(retained_media_ids)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if not isinstance(parsed, list) or not all(
            isinstance(x, str) for x in parsed
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="retained_media_ids must be a JSON array of strings.",
            )
        retained = parsed
    return await update_issue(
        issue_id, current_user.id, data, db, images, retained
    )


@router.post(
    "/{issue_id}/upvote", response_model=UpvoteResponse, status_code=status.HTTP_200_OK
)
async def upvote_issue(
    issue_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await toggle_vote(issue_id, current_user.id, db)
