from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Issue, Upvote


async def load_issue_vote_counts(db: AsyncSession, issues: list[Issue]) -> None:
    if not issues:
        return
    rows = await db.execute(
        select(Upvote.issue_id, func.count())
        .where(Upvote.issue_id.in_([issue.id for issue in issues]))
        .group_by(Upvote.issue_id)
    )
    counts = dict(rows.tuples().all())
    for issue in issues:
        issue.upvote_count = counts.get(issue.id, 0)
