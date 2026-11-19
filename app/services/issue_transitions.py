from datetime import datetime

from fastapi import HTTPException

from app.schemas.enum import IssueStatusEnum

ALLOWED_TRANSITIONS = {
    IssueStatusEnum.open: {IssueStatusEnum.in_progress, IssueStatusEnum.resolved, IssueStatusEnum.closed},
    IssueStatusEnum.in_progress: {IssueStatusEnum.open, IssueStatusEnum.resolved, IssueStatusEnum.closed},
    IssueStatusEnum.resolved: {IssueStatusEnum.in_progress, IssueStatusEnum.closed},
    IssueStatusEnum.closed: {IssueStatusEnum.open},
}


def resolution_timestamp(
    previous: IssueStatusEnum,
    current: IssueStatusEnum,
    resolved_at: datetime | None,
    now: datetime,
) -> datetime | None:
    if current == previous:
        return resolved_at
    if current not in ALLOWED_TRANSITIONS[previous]:
        raise HTTPException(409, f"Issue status cannot change from {previous.value} to {current.value}")
    if current == IssueStatusEnum.resolved:
        return now
    if current == IssueStatusEnum.closed and previous == IssueStatusEnum.resolved:
        return resolved_at
    return None
