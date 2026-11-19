from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.admin_config import NO_STORE
from app.dependencies.admin_deps import Database, require_admin
from app.schemas.admin_issues import (
    AdminIssueListResponse,
    AdminIssueQuery,
    AdminIssueResponse,
)
from app.services.admin_issue_service import get_admin_issue, list_admin_issues

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=AdminIssueListResponse)
async def admin_issues(
    response: Response, db: Database, query: Annotated[AdminIssueQuery, Query()]
):
    response.headers.update(NO_STORE)
    return await list_admin_issues(db, query)


@router.get("/{issue_id}", response_model=AdminIssueResponse)
async def admin_issue_detail(issue_id: str, response: Response, db: Database):
    response.headers.update(NO_STORE)
    return await get_admin_issue(db, issue_id)
