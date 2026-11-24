from datetime import UTC, datetime

from sqlalchemy import delete

from app.models.models import KycSubmission, User


async def check_admin_kyc(client, Session, admin_headers, citizen_headers, submission_id):
    path = f"/api/admin/kyc/{submission_id}"
    for headers, expected in (({}, 401), (citizen_headers, 403)):
        for endpoint in ("/api/admin/kyc", path):
            response = await client.get(endpoint, headers=headers)
            assert response.status_code == expected, response.text
    response = await client.get(path, headers=admin_headers)
    assert response.status_code == 200, response.text
    original = response.json()["data"]
    assert response.headers["Cache-Control"] == "private, no-store"
    assert original["user_id"] and original["id"] == submission_id
    assert (await client.get("/api/admin/kyc/missing", headers=admin_headers)).status_code == 404
    assert "user_id" not in (await client.get("/api/kyc/me", headers=citizen_headers)).json()["data"]
    for note in (None, "", "  "):
        response = await client.patch(path, headers=admin_headers, json={"status": "rejected", "note": note})
        assert response.status_code == 422, response.text
    assert (await client.get(path, headers=admin_headers)).json()["data"]["status"] == "pending"

    user_ids = [f"kyc-search-user-{index}" for index in range(3)]
    submission_ids = [f"kyc-search-sub-{index}" for index in range(3)]
    fields = ("citizenship_number", "gender", "date_of_birth", "issued_date", "ward_number",
              "province_name", "district_name", "municipality_name")
    async with Session() as session:
        source = await session.get(KycSubmission, submission_id)
        values = {field: getattr(source, field) for field in fields}
        session.add_all([User(id=user_id, email=f"{user_id}@example.com", password="unused") for user_id in user_ids])
        await session.flush()
        session.add_all([
            KycSubmission(
                **values, id=sub_id, user_id=user_id, full_name=f"Queue%_ Applicant {index}",
                status="pending" if index < 2 else "rejected",
                created_at=datetime(2026, 10, 15, 18, 14 + min(index, 1), tzinfo=UTC),
            ) for index, (sub_id, user_id) in enumerate(zip(submission_ids, user_ids))
        ])
        await session.commit()
    try:
        for page, expected in ((1, submission_ids[1]), (2, submission_ids[0]), (3, None)):
            response = await client.get("/api/admin/kyc", headers=admin_headers, params={
                "search": "  queue%_  ", "status": "pending", "page": page, "limit": 1,
            })
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert data["meta"] == {"total": 2, "page": page, "limit": 1, "total_pages": 2}
            assert [row["id"] for row in data["submissions"]] == ([expected] if expected else [])
            assert response.headers["Cache-Control"] == "private, no-store"
        for params, total in (({"search": "%_"}, 3), ({"search": "queue%_", "status": "rejected"}, 1),
                              ({"search": "no matching applicant"}, 0), ({"search": original["citizenship_number"]}, 4)):
            response = await client.get("/api/admin/kyc", headers=admin_headers, params=params)
            assert response.status_code == 200 and response.json()["data"]["meta"]["total"] == total, response.text
        for sort, expected in (("name_asc", submission_ids[1:]), ("name_desc", submission_ids[1:][::-1])):
            response = await client.get("/api/admin/kyc", headers=admin_headers, params={
                "search": "queue%_", "submitted_on": "2026-10-16", "sort": sort,
            })
            assert response.status_code == 200, response.text
            assert [row["id"] for row in response.json()["data"]["submissions"]] == expected
        response = await client.get("/api/admin/kyc", headers=admin_headers, params={"search": "x" * 201})
        assert response.status_code == 422
        response = await client.get("/api/admin/kyc", headers=admin_headers, params={"status": "invalid"})
        assert response.status_code == 400
        print("ok: admin KYC search filters before stable pagination, detail is protected, and rejection requires a reason")
    finally:
        async with Session() as session:
            await session.execute(delete(KycSubmission).where(KycSubmission.id.in_(submission_ids)))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
            await session.commit()
