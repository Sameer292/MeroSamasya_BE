from datetime import timedelta
from random import Random

from app.models.models import Issue, Upvote

def demo_vote_target(index: int) -> int:
    random = Random(5831 + index)
    # Most reports get modest engagement, with a smaller tail of popular reports.
    if random.random() < 0.06:
        return 0
    return round(40 * random.betavariate(1.65, 2.7))


def build_demo_upvotes(issue: Issue, index: int, voter_ids, existing=()) -> list[Upvote]:
    existing = set(existing)
    voters = [voter for voter in voter_ids if voter != issue.citizen_id and voter not in existing]
    target = demo_vote_target(index)
    missing = min(max(0, target - len(existing)), len(voters))
    selected = Random(1903 + index).sample(voters, missing)
    return [
        Upvote(issue=issue, user_id=voter, created_at=issue.created_at + timedelta(minutes=rank + 1))
        for rank, voter in enumerate(selected)
    ]
