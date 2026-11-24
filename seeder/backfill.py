"""Add missing examples to the deployed Hetauda demo without replacing user data."""

from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, engine
from app.core.storage import local_path
from app.models.admin_auth import AdminMembership
from app.models.issue_moderation import IssueModerationEvent
from app.models.models import Issue, IssueMedia, User
from app.schemas.enum import IssueStatusEnum
from seeder.assets import DemoPhotos
from seeder.catalog import ADMIN_EMAIL, REPORT_TEMPLATES, SITES
from seeder.report_examples import closed_report_event, report_detail_photo


async def demo_reviewer(db):
    return await db.scalar(
        select(User.id).join(AdminMembership, AdminMembership.user_id == User.id)
        .where(User.email == ADMIN_EMAIL, User.name == "Hetauda Demo Admin")
    )


async def find_demo_reports(db):
    expected = {
        (f"{template.title} | {site}", template.details, f"{site}, Hetauda, Makwanpur")
        for site, *_ in SITES for template in REPORT_TEMPLATES
    }
    candidates = await db.scalars(
        select(Issue).join(Issue.citizen)
        .where(Issue.deleted_at.is_(None), User.phone.like("980000%"),
               User.email.like("%@example.com"), Issue.address.like("%, Hetauda, Makwanpur"))
        .options(selectinload(Issue.media))
    )
    return [issue for issue in candidates if (issue.title, issue.description, issue.address) in expected]


def add_detail_attachment(db, issue, photos) -> bool:
    if len(issue.media) != 1:
        return False
    path = urlsplit(issue.media[0].url).path
    prefix = "/api/files/issues/"
    if not path.startswith(prefix):
        return False
    try:
        source = local_path("issues", path.removeprefix(prefix)).read_bytes()
    except (ValueError, FileNotFoundError):
        return False
    url = photos.add(db, "issues", report_detail_photo(source))
    issue.media.append(IssueMedia(url=url, created_at=issue.created_at))
    return True


async def add_closed_history(db, reports, reviewer_id: str) -> int:
    closed = {issue.id: issue for issue in reports if issue.status == IssueStatusEnum.closed}
    if not closed:
        return 0
    recorded = set(await db.scalars(
        select(IssueModerationEvent.issue_id).where(IssueModerationEvent.issue_id.in_(closed))
    ))
    missing = closed.keys() - recorded
    db.add_all(closed_report_event(closed[issue_id], reviewer_id) for issue_id in missing)
    return len(missing)


async def backfill_demo() -> str:
    photos = DemoPhotos()
    try:
        async with AsyncSessionLocal.begin() as db:
            reviewer = await demo_reviewer(db)
            if not reviewer:
                raise ValueError("No Hetauda demo reviewer found in the configured database.")
            reports = await find_demo_reports(db)
            events = await add_closed_history(db, reports, reviewer)
            attachments = sum(add_detail_attachment(db, issue, photos) for issue in reports)
            photos.write()
    except BaseException:
        photos.discard()
        raise
    finally:
        await engine.dispose()
    return f"Checked {len(reports)} demo reports. Added {events} moderation events and {attachments} attachments."
