from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.models.models import Issue
from app.schemas.enum import IssueStatusEnum


async def check_admin_map(client, Session, headers, original):
    bounds = {"south": 27, "north": 28, "west": 85, "east": 86}
    now = datetime.now(UTC)
    reports = [
        Issue(
            id=f"map-{index}",
            citizen_id=original["citizen_id"],
            category_id=original["category"]["id"],
            title="Viewport test",
            latitude=lat,
            longitude=lng,
            status=IssueStatusEnum.open,
            created_at=now + timedelta(seconds=index),
            deleted_at=now if index == 6 else None,
        )
        for index, (lat, lng) in enumerate(
            [(27, 85), (28, 86), (26.9, 85.5), (28.1, 85.5),
             (27.5, 84.9), (27.5, 86.1), (27.5, 85.5)]
        )
    ]
    async with Session() as session:
        session.add_all(reports)
        await session.commit()
    try:
        params = {**bounds, "search": "Viewport test", "limit": 1}
        for page, expected in ((1, "map-1"), (2, "map-0"), (3, None)):
            response = await client.get(
                "/api/admin/issues", headers=headers, params={**params, "page": page}
            )
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert data["meta"] == {"page": page, "limit": 1, "total": 2, "total_pages": 2}
            assert [issue["id"] for issue in data["issues"]] == ([expected] if expected else [])
        for extra in ({"status": "closed"}, {"south": 0, "north": 1}):
            data = (await client.get(
                "/api/admin/issues", headers=headers, params={**params, **extra}
            )).json()["data"]
            assert data["issues"] == [] and data["meta"]["total"] == 0
        invalid = [
            {"south": 27},
            {**bounds, "south": 29},
            {**bounds, "west": 87},
            {**bounds, "north": 91},
            {**bounds, "west": -181},
            {**bounds, "east": "nan"},
            {**bounds, "south": "inf"},
        ]
        for missing in bounds:
            invalid.append({key: value for key, value in bounds.items() if key != missing})
        for query in invalid:
            response = await client.get("/api/admin/issues", headers=headers, params=query)
            assert response.status_code == 422, (query, response.text)
        response = await client.get("/api/admin/issues", params=bounds)
        assert response.status_code == 401
        print("ok: admin map bounds validate, include edges, exclude deleted/outside pins and filter before pagination")
    finally:
        async with Session() as session:
            await session.execute(delete(Issue).where(Issue.id.in_([report.id for report in reports])))
            await session.commit()
