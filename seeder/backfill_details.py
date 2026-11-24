"""Refresh votes and document headings for the configured Hetauda demo."""

from collections import defaultdict
from itertools import product
from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.storage import local_path
from app.models.models import KycDocument, KycSubmission, Upvote, User
from app.schemas.enum import KycStatusEnum
from seeder.assets import DOCUMENT_TITLES, sample_document
from seeder.backfill import demo_reviewer, find_demo_reports
from seeder.catalog import REPORT_TEMPLATES, SITES
from seeder.demo_votes import build_demo_upvotes


def demo_identity_filters():
    return (
        KycSubmission.citizenship_number.like("DEMO-HTD-%"),
        User.email.like("%@example.com"),
        User.phone.like("980000%"),
    )


async def fill_demo_votes(db, reports):
    indexes = {
        f"{template.title} | {site[0]}": index
        for index, (site, template) in enumerate(product(SITES, REPORT_TEMPLATES))
    }
    voters = list(await db.scalars(
        select(User.id).join(KycSubmission)
        .where(*demo_identity_filters(), KycSubmission.status == KycStatusEnum.approved)
        .order_by(User.id)
    ))
    existing = defaultdict(list)
    for issue_id, voter_id in await db.execute(
        select(Upvote.issue_id, Upvote.user_id).where(Upvote.issue_id.in_([r.id for r in reports]))
    ):
        existing[issue_id].append(voter_id)
    added = [
        vote
        for issue in reports
        for vote in build_demo_upvotes(issue, indexes[issue.title], voters, existing[issue.id])
    ]
    db.add_all(added)
    return len(added)


def read_avatar(url):
    if not url:
        return None
    prefix = "/api/files/profiles/"
    path = urlsplit(url).path
    if not path.startswith(prefix):
        return None
    try:
        return local_path("profiles", path.removeprefix(prefix)).read_bytes()
    except (ValueError, FileNotFoundError):
        return None


async def refresh_demo_documents(db):
    rows = await db.execute(
        select(KycDocument, KycSubmission, User.profile_picture_url)
        .join(KycSubmission, KycSubmission.id == KycDocument.submission_id)
        .join(User, User.id == KycSubmission.user_id)
        .where(*demo_identity_filters(), KycDocument.kind.in_(DOCUMENT_TITLES))
    )
    updated = 0
    for document, submission, avatar_url in rows:
        avatar = read_avatar(avatar_url)
        if not avatar:
            continue
        data = sample_document(document.kind, submission.full_name, submission.citizenship_number, avatar)
        if document.data != data:
            document.data = data
            document.content_type = "image/jpeg"
            updated += 1
    return updated


async def backfill_demo_details():
    try:
        async with AsyncSessionLocal.begin() as db:
            if not await demo_reviewer(db):
                raise ValueError("No Hetauda demo reviewer found in the configured database.")
            reports = await find_demo_reports(db)
            votes = await fill_demo_votes(db, reports)
            documents = await refresh_demo_documents(db)
    finally:
        await engine.dispose()
    return f"Added {votes} demo upvotes and refreshed {documents} labeled KYC images."
