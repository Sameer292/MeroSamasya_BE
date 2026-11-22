"""Account deletion contract checks, run from tests/checks.py."""
import asyncio
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core import storage
from app.dependencies.auth_deps import get_current_user
from app.models.admin_auth import AdminSession
from app.models.models import (
    Issue,
    KycDocument,
    KycSubmission,
    Notification,
    Upvote,
    User,
    utcnow,
)
from app.models.photo_storage import PhotoObject
from app.models.refresh_token import RefreshToken
from app.schemas.enum import AccountStatusEnum
from app.services.photo_storage import PhotoChanges, clean_photo


async def check_account_deletion(client, session_factory, app, check, report_data, kyc_data, image, other_headers, admin_headers):
    email, password = "privacy@example.com", "private123"
    await client.post("/api/auth/register", json={
        "name": "Privacy Citizen", "phone": "9800000002", "email": email,
        "password": password, "confirm_password": password,
    })
    sessions = [(await client.post("/api/auth/login", json={"email": email, "password": password})).json()["data"]
                for _ in range(2)]
    user_id = sessions[0]["user_id"]
    headers = {"Authorization": f"Bearer {sessions[0]['access_token']}"}
    request = {**report_data, "submission_id": str(uuid4())}
    report = (await client.post("/api/issues/create", headers=headers, data=request, files=[("images", image)])).json()["data"]
    report_photo = report["media"][0]["url"]
    avatar = (await client.patch("/api/auth/me", headers=headers, files={"profile_picture": image})).json()["data"]["profile_picture_url"]
    kyc_files = [(field, image) for field in ("selfiePhoto", "documentFrontPhoto", "documentBackPhoto")]
    result = await client.post("/api/kyc/submit", headers=headers, data=kyc_data, files=kyc_files)
    check("deletion fixture has private identity documents", result.status_code == 201)
    await client.post(f"/api/issues/{report['id']}/upvote", headers=headers, json={"upvoted": True})
    async with session_factory() as db:
        stale_user = await db.get(User, user_id)
        submission = await db.scalar(select(KycSubmission).where(KycSubmission.user_id == user_id))
        submission_id = submission.id
        legacy_name = storage.local_name("image/jpeg")
        storage.write_local(image[1], "kyc", legacy_name)
        submission.selfie_path = legacy_name
        db.add(AdminSession(user_id=user_id, token_digest="deletion-session"))
        await db.commit()
    deletion = {"current_password": password}
    r = await client.request("DELETE", "/api/auth/me", json=deletion)
    check("account deletion requires authentication", r.status_code == 401)
    for body in ({}, {"current_password": ""}):
        r = await client.request("DELETE", "/api/auth/me", headers=headers, json=body)
        check("account deletion requires a nonempty password", r.status_code == 422)
    r = await client.request("DELETE", "/api/auth/me", headers=headers, json={"current_password": "incorrect"})
    check("wrong deletion password preserves account and documents", r.status_code == 400
          and (await client.get("/api/auth/me", headers=headers)).status_code == 200
          and (await client.get("/api/kyc/documents/front", headers=headers)).status_code == 200)
    check("another citizen cannot read identity documents", (await client.get(
        "/api/kyc/documents/front", headers=other_headers, params={"user_id": user_id}
    )).status_code == 403)
    r = await client.request("DELETE", "/api/auth/me", headers=admin_headers, json=deletion)
    check("citizen deletion endpoint excludes administrators", r.status_code == 403)

    async def fail_retire(*_):
        raise HTTPException(503, "Simulated cleanup reservation failure")

    with patch.object(PhotoChanges, "retire", fail_retire):
        r = await client.request("DELETE", "/api/auth/me", headers=headers, json=deletion)
    check("failed deletion rolls back personal data, civic links and sessions", r.status_code == 503
          and (await client.get("/api/auth/me", headers=headers)).status_code == 200
          and (await client.get("/api/kyc/documents/front", headers=headers)).status_code == 200
          and (await client.get(f"/api/issues/{report['id']}", headers=headers)).json()["data"]["citizen_id"] == user_id)

    r, racing_refresh = await asyncio.gather(
        client.request("DELETE", "/api/auth/me", headers=headers, json=deletion),
        client.post("/api/auth/refresh", json={"refresh_token": sessions[1]["refresh_token"]}),
    )
    check("reauthenticated citizen deletes account", r.status_code == 204)
    check("refresh racing deletion is rotated or rejected", racing_refresh.status_code in (200, 401))
    if racing_refresh.status_code == 200:
        sessions.append(racing_refresh.json()["data"])
    for tokens in sessions:
        check("all deleted account access sessions are revoked", (await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )).status_code == 401)
        check("all deleted account refresh sessions are revoked", (await client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )).status_code == 401)
    check("deleted credentials cannot sign in", (await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )).status_code == 401)
    check("owner loses document access", (await client.get("/api/kyc/documents/front", headers=headers)).status_code == 401)
    check("admin loses deleted document access", (await client.get(
        "/api/kyc/documents/front", headers=admin_headers, params={"user_id": user_id}
    )).status_code == 404)
    check("deleted avatar inaccessible and erased locally", (await client.get(avatar)).status_code == 404
          and not storage.stored_path("profiles", avatar.rsplit("/", 1)[1]).exists())
    check("legacy identity file erased", not storage.stored_path("kyc", legacy_name).exists())
    civic = (await client.get(f"/api/issues/{report['id']}", headers=other_headers)).json()["data"]
    check("civic report retains content and exact pin without author link", civic["citizen_id"] is None
          and all(civic[field] == report[field] for field in ("title", "description", "latitude", "longitude", "media", "status"))
          and (await client.get(report_photo)).status_code == 200)
    async with session_factory() as db:
        deleted = await db.get(User, user_id)
        check("only scrubbed account tombstone remains", deleted.account_status == AccountStatusEnum.deleted
              and deleted.deleted_at is not None and deleted.email != email and deleted.password != stale_user.password
              and all(getattr(deleted, field) is None for field in ("name", "phone", "location_id", "profile_picture_url")))
        for model, condition in (
            (KycSubmission, KycSubmission.user_id == user_id), (KycDocument, KycDocument.submission_id == submission_id),
            (Notification, Notification.user_id == user_id), (Upvote, Upvote.user_id == user_id),
            (RefreshToken, RefreshToken.user_id == user_id), (AdminSession, AdminSession.user_id == user_id),
        ):
            check(f"deletion erases {model.__name__}", await db.scalar(select(func.count()).select_from(model).where(condition)) == 0)
        check("retained civic report has no retry identifier", (await db.get(Issue, report["id"])).submission_id is None)

    # Simulate writes which already authenticated before deletion committed.
    app.dependency_overrides[get_current_user] = lambda: stale_user
    try:
        writes = [
            await client.patch("/api/auth/me", data={"name": "Restored Citizen"}),
            await client.post("/api/kyc/submit", data=kyc_data, files=kyc_files),
            await client.post("/api/issues/create", data={**request, "submission_id": str(uuid4())}, files=[("images", image)]),
            await client.patch(f"/api/issues/{report['id']}", data={"title": "Changed title"}),
            await client.post(f"/api/issues/{report['id']}/upvote", json={"upvoted": True}),
            await client.delete(f"/api/issues/{report['id']}"),
        ]
        check("in-flight citizen writes cannot restore deleted account data", all(r.status_code == 401 for r in writes))
    finally:
        app.dependency_overrides.pop(get_current_user)

    # A local filesystem failure stays queued and does not restore access.
    storage.write_local(image[1], "kyc", legacy_name)
    async with session_factory() as db:
        db.add(PhotoObject(url=f"/api/files/kyc/{legacy_name}", object_key=f"kyc/{legacy_name}", delete_after=deleted.deleted_at))
        await db.commit()
    with patch("pathlib.Path.unlink", side_effect=OSError("Simulated disk outage")):
        await clean_photo(f"/api/files/kyc/{legacy_name}")
    async with session_factory() as db:
        photo = await db.get(PhotoObject, f"/api/files/kyc/{legacy_name}")
        check("failed legacy document cleanup is durable and private", photo is not None and photo.delete_after is not None
              and (await client.get(f"/api/files/kyc/{legacy_name}")).status_code == 404)

        photo.delete_after = utcnow()
        await db.commit()
    await clean_photo(f"/api/files/kyc/{legacy_name}")
    async with session_factory() as db:
        check("legacy identity cleanup succeeds on retry", await db.get(PhotoObject, f"/api/files/kyc/{legacy_name}") is None
              and not storage.stored_path("kyc", legacy_name).exists())
    r = await client.post("/api/auth/register", json={
        "name": "New Citizen", "phone": "9800000002", "email": email,
        "password": password, "confirm_password": password,
    })
    check("deleted email can register a separate account", r.status_code == 201 and r.json()["data"]["user_id"] != user_id)
