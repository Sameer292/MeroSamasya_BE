"""Attachments and moderation events for the Hetauda demo reports."""

from datetime import timedelta
from io import BytesIO

from PIL import Image, ImageOps

from app.models.issue_moderation import IssueModerationEvent
from app.schemas.enum import IssueStatusEnum
from seeder.assets import jpeg


def report_detail_photo(photo: bytes) -> bytes:
    with Image.open(BytesIO(photo)) as original:
        image = ImageOps.exif_transpose(original)
        width, height = image.size
        return jpeg(image.crop((width // 6, height // 6, width * 5 // 6, height * 5 // 6)))


def closed_report_event(issue, reviewer_id: str):
    return IssueModerationEvent(
        issue_id=issue.id,
        reviewer_id=reviewer_id,
        created_at=issue.updated_at or issue.created_at + timedelta(hours=18),
        changes=[{
            "field": "status",
            "previous": IssueStatusEnum.open.value,
            "current": IssueStatusEnum.closed.value,
        }],
    )
