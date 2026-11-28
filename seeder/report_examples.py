"""Attachments and moderation events for the Hetauda demo reports."""

from datetime import timedelta
from io import BytesIO

from PIL import Image, ImageOps

from app.models.issue_moderation import IssueModerationEvent
from app.schemas.enum import IssueStatusEnum
from seeder.assets import jpeg


def report_detail_photo(photo: bytes, *, inset_divisor: int = 6) -> bytes:
    with Image.open(BytesIO(photo)) as original:
        image = ImageOps.exif_transpose(original)
        width, height = image.size
        horizontal = width // inset_divisor
        vertical = height // inset_divisor
        return jpeg(image.crop((horizontal, vertical, width - horizontal, height - vertical)))


def report_status_events(issue, reviewer_id: str):
    status = issue.status
    if status == IssueStatusEnum.open:
        return

    changed_at = issue.updated_at or issue.created_at + timedelta(hours=18)
    if status == IssueStatusEnum.resolved and issue.resolved_at:
        changed_at = issue.resolved_at
    previous = IssueStatusEnum.open

    if status == IssueStatusEnum.resolved:
        started_at = issue.created_at + (changed_at - issue.created_at) / 2
        yield status_event(issue.id, reviewer_id, started_at, previous, IssueStatusEnum.in_progress)
        previous = IssueStatusEnum.in_progress

    event = status_event(issue.id, reviewer_id, changed_at, previous, status)
    if status == IssueStatusEnum.resolved and issue.resolved_at:
        event.changes.append({
            "field": "resolved_at", "previous": None, "current": issue.resolved_at.isoformat(),
        })
    yield event


def status_event(issue_id, reviewer_id, changed_at, previous, current):
    return IssueModerationEvent(
        issue_id=issue_id,
        reviewer_id=reviewer_id,
        created_at=changed_at,
        changes=[{"field": "status", "previous": previous.value, "current": current.value}],
    )
