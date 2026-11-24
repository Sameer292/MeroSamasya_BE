from datetime import timedelta
from random import Random

from app.models.models import Issue, Upvote

VOTE_TARGETS = (
    0, 1, 5, 10, 15, 20, 30, 30, 30, 25, 30, 40, 30, 10, 5, 20,
    30, 30, 15, 30, 5, 30, 30, 20, 10, 30, 30, 30, 0, 1, 5, 10,
)


def build_demo_upvotes(issue: Issue, index: int, voter_ids, existing=()) -> list[Upvote]:
    existing = set(existing)
    voters = [voter for voter in voter_ids if voter != issue.citizen_id and voter not in existing]
    target = VOTE_TARGETS[index % len(VOTE_TARGETS)]
    missing = min(max(0, target - len(existing)), len(voters))
    selected = Random(1903 + index).sample(voters, missing)
    return [
        Upvote(issue=issue, user_id=voter, created_at=issue.created_at + timedelta(minutes=rank + 1))
        for rank, voter in enumerate(selected)
    ]
