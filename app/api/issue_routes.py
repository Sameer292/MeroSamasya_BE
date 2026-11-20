from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    UploadFile,
    Form,
)
from fastapi.exceptions import RequestValidationError
from typing import Annotated, Optional
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.schema import (
    IssueResponse,
    CitizenIssueQuery,
    IssueCreate,
    DeleteResponse,
    IssueUpdate,
    PaginatedIssueResponse,
    CategoryListResponse,
    UpvoteRequest,
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
    set_vote,
)
from app.services.category_service import get_categories
from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user

router = APIRouter()


class IssueCreateForm(IssueCreate):
    images: list[UploadFile] = []


class IssueUpdateForm(IssueUpdate):
    retained_media_ids: str | None = None
    images: list[UploadFile] = []


@router.post(
    "/create", response_model=IssueResponse, status_code=status.HTTP_201_CREATED
)
async def open_issue(
    data: Annotated[IssueCreateForm, Form(media_type="multipart/form-data")],
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    return await create_issue(data, current_user.id, db, data.images)


@router.get(
    "/me", response_model=PaginatedIssueResponse, status_code=status.HTTP_200_OK
)
async def my_issues(
    query: Annotated[CitizenIssueQuery, Query()],
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_my_issues(current_user.id, query, db)


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
    query: Annotated[CitizenIssueQuery, Query()],
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_all_issues(query, db, current_user.id)


@router.get(
    "/nearme",
    response_model=PaginatedIssueResponse,
    status_code=status.HTTP_200_OK,
)
async def issues_by_location(
    query: Annotated[CitizenIssueQuery, Query()],
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_issues_by_location(
        current_user.location_id, query, db, current_user.id
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
    data: Annotated[IssueUpdateForm, Form(media_type="multipart/form-data")],
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pin_fields = ("latitude", "longitude", "local_level_id")
    if data.model_fields_set.intersection(pin_fields):
        missing = [
            {"type": "missing", "loc": ("body", field), "msg": "Required when changing the report pin"}
            for field in pin_fields
            if getattr(data, field) is None
        ]
        if missing:
            raise RequestValidationError(missing)

    retained: list[str] | None = None
    if data.retained_media_ids:
        try:
            parsed = json.loads(data.retained_media_ids)
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
        issue_id, current_user.id, data, db, data.images, retained
    )


@router.post(
    "/{issue_id}/upvote", response_model=UpvoteResponse, status_code=status.HTTP_200_OK
)
async def upvote_issue(
    issue_id: str,
    request: UpvoteRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await set_vote(issue_id, current_user.id, request.upvoted, db)
