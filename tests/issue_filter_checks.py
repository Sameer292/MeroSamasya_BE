from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.models.models import Issue
from app.schemas.enum import IssueStatusEnum


async def check_issue_filters(
    client,
    Session,
    owner_headers,
    area_headers,
    original,
    category_id,
    other_category_id,
):
    now = datetime.now(UTC)
    reports = []
    for index in range(25):
        reports.append(
            Issue(
                id=f"filter-filler-{index}",
                citizen_id=original["citizen_id"],
                category_id=category_id,
                title="Unrelated newer report",
                status=IssueStatusEnum.open,
                latitude=original["latitude"],
                longitude=original["longitude"],
                local_level_id=original["local_level_id"],
                created_at=now + timedelta(seconds=index),
            )
        )
    for suffix, state, changes in (
        ("title", "open", {"title": "FilterNeedle 100%_literal काठमाडौं"}),
        ("description", "open", {"description": "FilterNeedle description"}),
        ("address", "in_progress", {"address": "FilterNeedle address"}),
        ("resolved", "resolved", {}),
        ("closed", "closed", {}),
        ("category", "open", {"category_id": other_category_id}),
        ("outside", "open", {"local_level_id": "outside"}),
        ("other-owner", "open", {"citizen_id": None}),
        ("deleted", "open", {"deleted_at": now}),
    ):
        reports.append(
            Issue(
                **{
                    "id": f"filter-{suffix}",
                    "citizen_id": original["citizen_id"],
                    "category_id": category_id,
                    "title": "FilterNeedle report",
                    "status": IssueStatusEnum(state),
                    "latitude": original["latitude"],
                    "longitude": original["longitude"],
                    "local_level_id": original["local_level_id"],
                    "created_at": now - timedelta(days=1),
                    **changes,
                }
            )
        )
    async with Session() as session:
        session.add_all(reports)
        await session.commit()
    try:
        for endpoint, headers, excluded in (
            ("all", owner_headers, set()),
            ("me", owner_headers, {"filter-other-owner"}),
            ("nearme", area_headers, {"filter-outside"}),
        ):
            path = f"/api/issues/{endpoint}"
            first = (
                await client.get(path, headers=headers, params={"limit": 20})
            ).json()["data"]
            assert "filter-title" not in {report["id"] for report in first["issues"]}
            params = {
                "search": "  fIlTeRnEeDlE  ",
                "category_id": category_id,
                "limit": 2,
            }
            response = await client.get(path, headers=headers, params=params)
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            expected = {
                f"filter-{suffix}"
                for suffix in (
                    "title",
                    "description",
                    "address",
                    "resolved",
                    "closed",
                    "outside",
                    "other-owner",
                )
            } - excluded
            assert data["meta"]["total"] == len(expected), (endpoint, data)
            assert data["meta"]["total_pages"] == (len(expected) + 1) // 2
            assert data["status_counts"] == {
                "open": len(expected) - 3,
                "in_progress": 1,
                "resolved": 1,
                "closed": 1,
            }
            found = []
            for page in range(1, data["meta"]["total_pages"] + 1):
                result = await client.get(
                    path, headers=headers, params={**params, "page": page}
                )
                found.extend(report["id"] for report in result.json()["data"]["issues"])
            assert len(found) == len(set(found)) and set(found) == expected
            result = await client.get(
                path, headers=headers, params={**params, "status": "closed"}
            )
            closed = result.json()["data"]
            assert (
                closed["meta"]["total"] == 1
                and closed["issues"][0]["id"] == "filter-closed"
            )
            assert closed["status_counts"] == data["status_counts"]
            for search, expected_id in (
                ("100%_literal", "filter-title"),
                ("काठमाडौं", "filter-title"),
                ("FilterNeedle description", "filter-description"),
                ("FilterNeedle address", "filter-address"),
            ):
                result = await client.get(
                    path, headers=headers, params={"search": search}
                )
                matched = result.json()["data"]
                assert (
                    matched["meta"]["total"] == 1
                    and matched["issues"][0]["id"] == expected_id
                )
            category = await client.get("/api/category/", headers=headers)
            other_name = next(
                item["name"]
                for item in category.json()["data"]
                if item["id"] == other_category_id
            )
            result = await client.get(
                path, headers=headers, params={"search": other_name}
            )
            assert [item["id"] for item in result.json()["data"]["issues"]] == [
                "filter-category"
            ]
            blank = await client.get(path, headers=headers, params={"search": "   "})
            assert blank.json()["data"]["meta"]["total"] == first["meta"]["total"]
            result = await client.get(
                path,
                headers=headers,
                params={"search": "100%_literal", "status": "resolved"},
            )
            unmatched_status = result.json()["data"]
            assert (
                unmatched_status["issues"] == []
                and unmatched_status["meta"]["total"] == 0
            )
            assert unmatched_status["status_counts"] == {
                "open": 1,
                "in_progress": 0,
                "resolved": 0,
                "closed": 0,
            }
            for params in (
                {"search": "no-matching-report"},
                {"category_id": "unknown"},
            ):
                result = await client.get(path, headers=headers, params=params)
                empty = result.json()["data"]
                assert empty["issues"] == [] and empty["meta"]["total"] == 0
                assert sum(empty["status_counts"].values()) == 0
            for params in ({"status": "invalid"}, {"search": "x" * 201}):
                assert (
                    await client.get(path, headers=headers, params=params)
                ).status_code == 422
            print(
                f"ok: {endpoint} filters before pagination, stable pages, matched counts, scope and validation"
            )
    finally:
        async with Session() as session:
            await session.execute(
                delete(Issue).where(Issue.id.in_([report.id for report in reports]))
            )
            await session.commit()
