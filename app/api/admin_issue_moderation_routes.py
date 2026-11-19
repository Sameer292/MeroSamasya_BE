from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.dependencies.admin_deps import Database, require_admin, verify_admin_origin
from app.dependencies.auth_deps import BearerCredentials
from app.models.models import User
from app.schemas.issue_moderation import (
    IssueModerationRequest,
    IssueModerationResponse,
    ModerationHistoryResponse,
)
from app.services.issue_moderation_service import list_moderation_events, moderate_issue

router = APIRouter()
Reviewer = Annotated[User, Depends(require_admin)]


async def authorize_moderation(
    request: Request, reviewer: Reviewer, credentials: BearerCredentials
) -> User:
    if credentials is None:
        await verify_admin_origin(request)
    return reviewer


@router.post(
    "/{issue_id}/moderation",
    response_model=IssueModerationResponse,
)
async def save_issue_moderation(
    issue_id: str,
    request: IssueModerationRequest,
    reviewer: Annotated[User, Depends(authorize_moderation)],
    db: Database,
):
    return {"data": await moderate_issue(db, issue_id, reviewer.id, request)}


@router.get(
    "/{issue_id}/moderation",
    response_model=ModerationHistoryResponse,
    dependencies=[Depends(require_admin)],
)
async def issue_moderation_history(issue_id: str, db: Database, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return {"data": await list_moderation_events(db, issue_id)}
