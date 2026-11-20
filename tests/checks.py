"""Runnable contract checks for the citizen grievance flow.

Runs the real app over ASGI against a temp SQLite DB with uploads on local
disk. No network, no Cloudinary, no pytest needed:
    .venv/bin/python tests/checks.py
"""

import asyncio
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

TMP = tempfile.mkdtemp(prefix="merosamasya-checks-")
os.environ["LOCAL_STORAGE_DIR"] = os.path.join(TMP, "storage")
os.environ["ADMIN_WEB_ORIGIN"] = "https://admin.test"
os.environ["ADMIN_COOKIE_SECURE"] = "true"
for key in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
    os.environ[key] = ""
os.environ.setdefault("JWT_SECRET", "merosamasya-local-contract-test-not-a-secret")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(TMP, "checks.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"

PASS = []


def check(name, cond):
    assert cond, f"FAILED: {name}"
    PASS.append(name)
    print(f"ok: {name}")


async def main():
    import httpx
    import jwt
    from PIL import Image
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    import main as app_module
    from app.core import storage as storage_config
    from app.core.database import Base, get_db
    from app.core.migrations import backfill_report_areas, run_startup_migrations
    from app.models import (
        models,  # noqa: F401
        nepal_location_models,  # noqa: F401
    )
    from app.models.admin_auth import AdminMembership
    from app.models.models import Issue, User
    from app.models.nepal_location_models import District, LocalLevel, Province
    from app.models.refresh_token import RefreshToken
    from app.schemas.enum import AccountStatusEnum, LocalLevelType
    from app.services.auth_service import hash_password
    from app.services.category_service import ensure_default_categories
    from app.services.jwt_tokens import JWT_ALGORITHM, JWT_SECRET
    from app.services.kyc_service import import_legacy_kyc_documents
    from app.services.nepal_location_service import load_bundled_seed
    from app.services.password_change import replace_password
    from app.services.report_area_service import boundaries
    from app.services.token_digest import digest_token

    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    _, area_names, _ = boundaries()
    check("boundary catalog covers every seeded local level", len(area_names) == 753 and {
        names[0] for names in area_names
    } == {
        (district, name)
        for districts in load_bundled_seed().values()
        for district, types in districts.items()
        for names in types.values()
        for name in names
    })

    async with Session() as s:
        await ensure_default_categories(s)
        prov = Province(name="बागमती प्रदेश")
        s.add(prov)
        await s.flush()
        dist = District(name="ललितपुर", province_id=prov.id)
        report_dist = District(name="काठमाण्डौं", province_id=prov.id)
        other_dist = District(name="भक्तपुर", province_id=prov.id)
        old_report_dist = District(name="Kathmandu", province_id=prov.id)
        s.add_all([dist, report_dist, other_dist, old_report_dist])
        await s.flush()
        home = LocalLevel(name="ललितपुर महानगरपालिका", type=LocalLevelType.MA_NA_PA, district_id=dist.id)
        report = LocalLevel(name="काठमाण्डौं महानगरपालिका", type=LocalLevelType.MA_NA_PA, district_id=report_dist.id)
        other = LocalLevel(name="भक्तपुर नगरपालिका", type=LocalLevelType.NA_PA, district_id=other_dist.id)
        old_report = LocalLevel(name="Kathmandu", type=LocalLevelType.MA_NA_PA, district_id=old_report_dist.id)
        s.add_all([home, report, other, old_report])
        await s.commit()
        level_id, report_level_id, other_level_id, old_report_level_id = (
            str(level.id) for level in (home, report, other, old_report)
        )

    async def override_db():
        async with Session() as session:
            yield session

    app_module.app.dependency_overrides[get_db] = override_db

    transport = httpx.ASGITransport(app=app_module.app)
    def image_file(fmt, color, size=(64, 64)):
        with BytesIO() as buffer:
            Image.new("RGB", size, color).save(buffer, format=fmt)
            return (f"photo.{fmt.lower()}", buffer.getvalue(), f"image/{fmt.lower()}")

    IMG = image_file("JPEG", "red")
    IMG2 = image_file("PNG", "green")
    webp = image_file("WEBP", "blue")
    fake_jpeg = ("photo.jpg", b"\xff\xd8\xff" + b"x" * 100, "image/jpeg")
    too_large = ("photo.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")
    too_wide = image_file("PNG", "green", size=(8193, 1))

    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        # --- auth ---
        signup = {
            "name": "  राम शर्मा  ", "phone": "9800000001", "email": "Test@Example.com",
            "password": "pass1234", "confirm_password": "pass1234"}
        for field, value in (("name", "राम1"), ("confirm_password", "different1")):
            r = await c.post("/api/auth/register", json={**signup, field: value})
            errors = r.json()["detail"]
            check(f"register returns a field error for {field}", r.status_code == 422
                  and errors[0]["loc"] == ["body", field]
                  and set(errors[0]) == {"loc", "msg", "type"})
        r = await c.post("/api/auth/register", json=signup)
        check("register accepts a Devanagari name", r.status_code == 201)
        r = await c.post("/api/auth/register", json={
            "name": "Test User", "phone": "9800000001", "email": "test@example.com",
            "password": "pass1234", "confirm_password": "pass1234"})
        check("duplicate register 400", r.status_code == 400)
        r = await c.post("/api/auth/login", json={"email": "TEST@example.com", "password": "pass1234"})
        check("login normalizes case 200", r.status_code == 200)
        tokens = r.json()["data"]
        owner_id = tokens["user_id"]
        H = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = await c.get("/api/auth/me", headers=H)
        check("register stores the trimmed name", r.json()["data"]["name"] == "राम शर्मा")
        r = await c.post("/api/auth/login", json={"email": "test@example.com", "password": "wrongpass1"})
        check("wrong password 401", r.status_code == 401)
        concurrent_refreshes = await asyncio.gather(*(
            c.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
            for _ in range(2)
        ))
        check("concurrent refresh has one winner",
              sorted(r.status_code for r in concurrent_refreshes) == [200, 401])
        rotated_refresh = next(r.json()["data"]["refresh_token"]
                               for r in concurrent_refreshes if r.status_code == 200)
        r = await c.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        check("consumed refresh token rejected", r.status_code == 401)
        r = await c.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
        check("access-as-refresh 401", r.status_code == 401)
        r = await c.post("/api/auth/refresh", json={"refresh_token": "garbage"})
        check("garbage refresh 401 not 500", r.status_code == 401)

        # An existing session upgrades on refresh. Logout may still receive its old token.
        expires = datetime.now(UTC) + timedelta(days=1)
        legacy_jwt = {"sub": owner_id, "exp": expires}
        legacy_access = jwt.encode({**legacy_jwt, "refresh": False}, JWT_SECRET, algorithm=JWT_ALGORITHM)
        legacy_refresh = jwt.encode({**legacy_jwt, "refresh": True}, JWT_SECRET, algorithm=JWT_ALGORITHM)
        async with Session() as s:
            s.add(RefreshToken(user_id=owner_id, token_digest=digest_token(legacy_refresh),
                               expires_at=int(expires.timestamp())))
            await s.commit()
        r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy_access}"})
        check("legacy access requires a refresh", r.status_code == 401)
        r = await c.post("/api/auth/refresh", json={"refresh_token": legacy_refresh})
        check("legacy refresh upgrades the session", r.status_code == 200)
        second_device = r.json()["data"]
        second_headers = {"Authorization": f"Bearer {second_device['access_token']}"}
        r = await c.get("/api/auth/me", headers=second_headers)
        check("upgraded session can access account", r.status_code == 200)
        for _ in range(2):
            r = await c.post("/api/auth/logout", json={"refresh_token": legacy_refresh})
            check("logout with a rotated refresh token is idempotent", r.status_code == 204)
        r = await c.post("/api/auth/refresh", json={"refresh_token": second_device["refresh_token"]})
        check("logged-out session cannot refresh its newest token", r.status_code == 401)
        r = await c.get("/api/auth/me", headers=second_headers)
        check("logged-out session loses bearer access", r.status_code == 401)

        r = await c.post("/api/auth/login", json={"email": "test@example.com", "password": "pass1234"})
        refresh_body = {"refresh_token": r.json()["data"]["refresh_token"]}
        refreshed, logged_out = await asyncio.gather(
            c.post("/api/auth/refresh", json=refresh_body),
            c.post("/api/auth/logout", json=refresh_body),
        )
        check("logout racing refresh succeeds", logged_out.status_code == 204
              and refreshed.status_code in (200, 401))
        if refreshed.status_code == 200:
            refresh_body = {"refresh_token": refreshed.json()["data"]["refresh_token"]}
        r = await c.post("/api/auth/refresh", json=refresh_body)
        check("no active refresh token survives racing logout", r.status_code == 401)

        r = await c.get("/api/auth/me", headers=H)
        check("other session stays active and returns citizen role and null location", r.status_code == 200
              and r.json()["data"]["location"] is None and r.json()["data"]["role"] == "citizen")

        # suspended user blocked everywhere
        async with Session() as s:
            u = (await s.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
            u.account_status = AccountStatusEnum.suspended
            await s.commit()
        r = await c.get("/api/auth/me", headers=H)
        check("suspended /me 403", r.status_code == 403)
        r = await c.post("/api/auth/refresh", json={"refresh_token": rotated_refresh})
        check("suspended refresh 403", r.status_code == 403)
        async with Session() as s:
            u = (await s.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
            u.account_status = AccountStatusEnum.active
            await s.commit()

        # --- categories ---
        r = await c.get("/api/issues/categories")
        check("mobile categories alias 200", r.status_code == 200 and len(r.json()["data"]) == 9)
        cat_id = r.json()["data"][0]["id"]
        r = await c.post("/api/category/", json={"name": "X", "icon": "i", "color": "#fff"})
        check("category write unauth 401", r.status_code == 401)
        r = await c.post("/api/category/", headers=H, json={"name": "Parks", "icon": "ri-tree", "color": "#fff"})
        check("citizen category write 403", r.status_code == 403)
        admin_login = {"email": "admin@example.com", "password": "pass1234"}
        r = await c.post("/api/auth/register", json={
            **admin_login, "confirm_password": "pass1234", "name": "Test Admin", "phone": "9800000003"})
        admin_id = r.json()["data"]["user_id"]
        async with Session() as s:
            s.add(AdminMembership(user_id=admin_id, role="admin"))
            await s.commit()
        r = await c.post("/api/auth/login", json=admin_login)
        AH = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        r = await c.post("/api/category/", json={"name": "Parks", "icon": "ri-tree", "color": "#fff"}, headers=AH)
        check("admin create category 201", r.status_code == 201)
        new_cat = r.json()["data"]["id"]
        r = await c.post("/api/category/", json={"name": "Parks", "icon": "i", "color": "#fff"}, headers=AH)
        check("duplicate category 400", r.status_code == 400)
        other = r.json()  # noqa: F841
        r = await c.patch(f"/api/category/{new_cat}", json={"name": r.json() and "Roads & Transport"}, headers=AH)
        check("rename to existing 400", r.status_code == 400)

        # --- locations ---
        r = await c.get("/api/location/locations")
        check("locations list has seeded level", r.status_code == 200 and any(
            x["id"] == str(level_id) for x in r.json()["data"]))
        r = await c.patch("/api/location/location", json={"location_id": str(level_id)}, headers=H)
        check("set location 200 with name", r.status_code == 200
              and r.json()["data"]["location"] == {"id": str(level_id), "name": "ललितपुर महानगरपालिका"})
        r = await c.patch("/api/location/location", json={"location_id": "999999"}, headers=H)
        check("bad location 404", r.status_code == 404)

        # --- issues ---
        r = await c.get("/api/issues/all?page=0", headers=H)
        check("page=0 -> 422", r.status_code == 422)
        files = [("images", IMG)]
        report_data = {
            "category_id": cat_id, "title": "  Pothole on Main Road's <detour> & lane  \t",
            "latitude": "27.710", "longitude": "85.324",
            "local_level_id": report_level_id,
        }
        pin = {key: report_data[key] for key in ("latitude", "longitude")}
        r = await c.get("/api/location/report-areas", params=pin)
        check("pin lookup returns the current municipality ID", r.status_code == 200
              and r.json()["data"] == [{"id": report_level_id, "name": "काठमाण्डौं महानगरपालिका"}])
        r = await c.get("/api/location/report-areas", params={"latitude": "0", "longitude": "0"})
        check("pin outside supported boundaries has no choices", r.status_code == 200 and r.json()["data"] == [])
        r = await c.get("/api/location/report-areas", params={**pin, "latitude": "120"})
        check("area lookup rejects out-of-range latitude with a field error", r.status_code == 422
              and r.json()["detail"][0]["loc"] == ["query", "latitude"])
        r = await c.post("/api/issues/create", headers=H, data=report_data, files=files)
        check("create without desc/addr 201", r.status_code == 201)
        issue = r.json()["data"]
        check("create trims title and preserves plain text", issue["title"] == report_data["title"].strip())
        check("explicit report area differs from residence", issue["local_level_id"] == str(report_level_id))
        check("local media url", issue["media"][0]["url"].startswith("/api/files/issues/"))
        r = await c.get(issue["media"][0]["url"])
        check("stored photo served 200 without caching", r.status_code == 200
              and r.headers["Cache-Control"] == "no-store")
        iid = issue["id"]
        issue_photo = issue["media"][0]["url"]
        r = await c.patch(f"/api/issues/{iid}", headers=H, data={"title": issue["title"]})
        check("report with missing optional text can be edited", r.status_code == 200
              and r.json()["data"]["description"] is None and r.json()["data"]["address"] is None)
        for field, invalid in (("latitude", "120"), ("latitude", "nan"), ("longitude", "-181"),
                               ("longitude", "inf"), ("description", "  abc  ")):
            payload = {**report_data, field: invalid}
            r = await c.post("/api/issues/create", headers=H, data=payload, files=files)
            check(f"create rejects invalid {field} ({invalid}) with a field error",
                  r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", field])
            r = await c.patch(f"/api/issues/{iid}", headers=H, data={**pin, field: invalid})
            check(f"edit rejects invalid {field} ({invalid}) with a field error",
                  r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", field])
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"description": "  Road damage  ", "address": "  काठमाडौं  "})
        check("edit trims report text", r.status_code == 200
              and r.json()["data"]["description"] == "Road damage" and r.json()["data"]["address"] == "काठमाडौं")
        r = await c.patch(f"/api/issues/{iid}", headers=H, data={"description": "", "address": " "})
        check("edit can clear optional report text", r.status_code == 200
              and r.json()["data"]["description"] is None and r.json()["data"]["address"] is None)
        for invalid_title in ("", " \t ", "  ab  ", "x" * 201):
            r = await c.post("/api/issues/create", headers=H,
                             data={**report_data, "title": invalid_title}, files=files)
            check("create rejects an invalid title", r.status_code == 422
                  and r.json()["detail"][0]["loc"] == ["body", "title"])
            r = await c.patch(f"/api/issues/{iid}", headers=H, data={"title": invalid_title}, files=files)
            check("edit rejects an invalid title", r.status_code == 422
                  and r.json()["detail"][0]["loc"] == ["body", "title"])
        r = await c.post("/api/issues/create", headers=H, data={**report_data, "category_id": "nope"}, files=files)
        check("bad category 404", r.status_code == 404)
        r = await c.post("/api/issues/create", headers=H, data=report_data)
        check("no images 400", r.status_code == 400)
        r = await c.post("/api/issues/create", headers=H, data=report_data,
            files=[("images", ("t.txt", b"hi", "text/plain"))])
        check("bad file type 400", r.status_code == 400)
        for invalid, message in [
            (fake_jpeg, "JPEG, PNG, or WebP"),
            ((IMG[0], IMG[1][:-30], IMG[2]), "JPEG, PNG, or WebP"),
            (too_large, "5 MB"),
            (too_wide, "dimensions"),
        ]:
            r = await c.post("/api/issues/create", headers=H, data=report_data, files=[("images", invalid)])
            check(f"report image validation: {message}", r.status_code == 400
                  and r.json()["detail"][0]["loc"] == ["body", "images", 0]
                  and message in r.json()["detail"][0]["msg"])
        r = await c.patch(f"/api/issues/{iid}", headers=H, files=[("images", fake_jpeg)])
        check("edit validates replacement image bytes", r.status_code == 400
              and r.json()["detail"][0]["loc"] == ["body", "images", 0])
        storage = Path(os.environ["LOCAL_STORAGE_DIR"]) / "issues"
        before_upload = set(storage.iterdir())
        r = await c.post("/api/issues/create", headers=H, data=report_data,
                         files=[("images", IMG), ("images", ("empty.jpg", b"", "image/jpeg"))])
        check("failed multipart upload leaves no unreferenced file",
              r.status_code == 400 and set(storage.iterdir()) == before_upload)

        for path in (f"/api/issues/{iid}", "/api/issues/me", "/api/issues/all", "/api/issues/nearme"):
            r = await c.get(path, headers=H, params={"page": 1, "limit": 10} if "{" not in path else None)
            check(f"read {path} 200", r.status_code == 200)
        r = await c.get("/api/issues/nearme", headers=H)
        check("residence feed excludes report across municipal boundary", r.json()["data"]["meta"]["total"] == 0)

        # --- second user + votes ---
        r = await c.post("/api/auth/register", json={
            "name": "Voter Two", "phone": "9800000002", "email": "voter2@example.com",
            "password": "pass1234", "confirm_password": "pass1234"})
        r = await c.post("/api/auth/login", json={"email": "voter2@example.com", "password": "pass1234"})
        H2 = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
        r = await c.patch("/api/location/location", json={"location_id": old_report_level_id}, headers=H2)
        check("reader can select report municipality", r.status_code == 200)
        r = await c.get("/api/issues/nearme", headers=H2)
        check("report appears in its municipality with a legacy profile ID", [x["id"] for x in r.json()["data"]["issues"]] == [iid])
        r = await c.post("/api/issues/create", headers=H, data={**report_data, "local_level_id": level_id}, files=files)
        check("create rejects a pin outside its selected municipality", r.status_code == 400)
        r = await c.post("/api/issues/create", headers=H,
                         data={key: value for key, value in report_data.items() if key != "local_level_id"}, files=files)
        check("create requires municipality even when residence is saved", r.status_code == 422)
        r = await c.patch("/api/location/location", json={"location_id": other_level_id}, headers=H)
        check("reporter changes residence to a third municipality", r.status_code == 200)
        r = await c.get("/api/issues/nearme", headers=H2)
        check("report stays in original municipal feed after reporter moves", [x["id"] for x in r.json()["data"]["issues"]] == [iid])

        r = await c.patch(f"/api/issues/{iid}", headers=H, data={"latitude": "27.673"})
        check("edit requires municipality and both coordinates together", r.status_code == 422
              and {error["loc"][-1] for error in r.json()["detail"]} == {"longitude", "local_level_id"})
        moved_pin = {"latitude": "27.673", "longitude": "85.324", "local_level_id": level_id}
        r = await c.patch(f"/api/issues/{iid}", headers=H, data={**moved_pin, "local_level_id": report_level_id})
        check("edit rejects a pin outside its selected municipality", r.status_code == 400)
        moved = await c.patch(f"/api/issues/{iid}", headers=H, data=moved_pin)
        check("pin edit saves coordinates and municipality together", moved.status_code == 200
              and moved.json()["data"]["local_level_id"] == level_id
              and moved.json()["data"]["latitude"] == 27.673)
        r = await c.get("/api/issues/nearme", headers=H2)
        check("moved report leaves the previous municipal feed", r.json()["data"]["issues"] == [])
        r = await c.patch("/api/location/location", json={"location_id": level_id}, headers=H2)
        r = await c.get("/api/issues/nearme", headers=H2)
        check("moved report appears in its new municipal feed", [x["id"] for x in r.json()["data"]["issues"]] == [iid])
        r = await c.post(f"/api/issues/{iid}/upvote", headers=H2)
        body = r.json()
        check("upvote 200 count 1", r.status_code == 200 and body["data"]["upvote_count"] == 1
              and body["data"]["upvoted"] is True)
        r = await c.get("/api/notifications", headers=H)
        notifs = r.json()["data"]
        check("owner notified of upvote", any(n["type"] == "upvote" for n in notifs["notifications"]))
        check("unread_count > 0", notifs["unread_count"] >= 1)
        nid = notifs["notifications"][0]["id"]
        r = await c.patch(f"/api/notifications/{nid}/read", headers=H)
        check("mark single read 200", r.status_code == 200 and r.json()["data"]["read"] is True
              and r.json()["data"]["id"] == nid)
        # self-vote creates no notification
        before = (await c.get("/api/notifications", headers=H)).json()["data"]["meta"]["total"]
        await c.post(f"/api/issues/{iid}/upvote", headers=H)
        after = (await c.get("/api/notifications", headers=H)).json()["data"]["meta"]["total"]
        check("self-vote silent", after == before)
        await c.post(f"/api/issues/{iid}/upvote", headers=H)  # unvote self
        r = await c.post(f"/api/issues/{iid}/upvote", headers=H2)  # unvote voter2
        check("unvote count 0", r.json()["data"]["upvote_count"] == 0
              and r.json()["data"]["upvoted"] is False)

        # --- edit media retain ---
        import json as jsonlib
        # --- edit media retain (mobile sends retained_media_ids JSON string) ---
        edited_title = "Updated title: it's the <same> road & lane"
        edited_title += "!" * (200 - len(edited_title))
        r = await c.patch(f"/api/issues/{iid}", headers=H, data={"title": f"  {edited_title}  "},
                          files=[("images", IMG2)])
        check("edit replace-all legacy 200", r.status_code == 200 and len(r.json()["data"]["media"]) == 1)
        check("edit trims a 200-character title and preserves plain text", r.json()["data"]["title"] == edited_title)
        check("replaced issue photo URL returns 404", (await c.get(issue_photo)).status_code == 404)
        check("metadata edit preserves the saved pin", (r.json()["data"]["latitude"], r.json()["data"]["local_level_id"])
              == (27.673, level_id))
        kept = r.json()["data"]["media"][0]["id"]
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps([kept])},
                          files=[("images", IMG), ("images", IMG2)])
        check("retain 1 + add 2 = 3", r.status_code == 200 and len(r.json()["data"]["media"]) == 3)
        check("omitting a title preserves it", r.json()["data"]["title"] == edited_title)
        gallery = {media["id"]: media["url"] for media in r.json()["data"]["media"]}
        before_upload = set(storage.iterdir())
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps(["no-such-id"])},
                          files=[("images", IMG)])
        check("failed edit leaves the existing gallery intact and no additional file",
              r.status_code == 400 and set(storage.iterdir()) == before_upload)
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps([kept])},
                          files=[("images", IMG), ("images", IMG2), ("images", IMG)])
        check("retain+add over limit 400", r.status_code == 400)
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": "not-json"})
        check("malformed retain list 400", r.status_code == 400)
        # explicit [] + no new files cannot empty the gallery
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps([])})
        check("explicit empty retain 400", r.status_code == 400)
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps([kept])})
        check("remove-only edit preserves the retained photo", r.status_code == 200
              and (await c.get(gallery[kept])).status_code == 200)
        for media_id, url in gallery.items():
            if media_id != kept:
                check("removed photo URL returns 404 and file is gone",
                      (await c.get(url)).status_code == 404 and not (storage / Path(url).name).exists())
        # explicit [] + new files = replace with new
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps([])},
                          files=[("images", IMG)])
        check("explicit empty retain + 1 new = 1", r.status_code == 200
              and len(r.json()["data"]["media"]) == 1)
        r = await c.patch(f"/api/issues/{iid}", headers=H, data={"category_id": "nope"})
        check("edit bad category 404", r.status_code == 404)
        r = await c.delete(f"/api/issues/{iid}", headers=H2)
        check("delete non-owner 403", r.status_code == 403)

        # --- profile + password (mobile: PATCH /api/auth/me, POST change-password) ---
        for name in ("", "  ", "राम1"):
            r = await c.patch("/api/auth/me", headers=H, data={"name": name})
            check("profile rejects invalid name with a field error", r.status_code == 422
                  and r.json()["detail"][0]["loc"] == ["body", "name"])
        r = await c.patch("/api/auth/me", headers=H, data={
            "name": "  सीता श्रेष्ठ  ", "phone": "9800000009", "location_id": other_level_id},
            files=[("profile_picture", IMG)])
        check("profile update accepts and trims a Devanagari name", r.status_code == 200
              and r.json()["data"]["name"] == "सीता श्रेष्ठ")
        avatar = r.json()["data"]["profile_picture_url"]
        r = await c.patch("/api/auth/me", headers=H, files={
            "name": (None, "सीता शर्मा"), "location_id": (None, level_id)})
        saved_profile = r.json()["data"]
        check("profile update returns the saved name and municipality together", r.status_code == 200
              and saved_profile["name"] == "सीता शर्मा"
              and saved_profile["location"] == {"id": level_id, "name": home.name})
        r = await c.get("/api/auth/me", headers=H)
        check("reopening profile returns the same saved profile", r.status_code == 200
              and r.json()["data"] == saved_profile)
        r = await c.patch("/api/auth/me", headers=H, files=[("profile_picture", too_large)])
        check("oversized avatar returns a field error and preserves the previous image",
              r.status_code == 400 and r.json()["detail"][0]["loc"] == ["body", "profile_picture"]
              and (await c.get(avatar)).status_code == 200)
        r = await c.patch("/api/auth/me", headers=H,
                          files=[("profile_picture", ("old-app.jpg", webp[1], "image/jpeg"))])
        check("replaced avatar URL returns 404", r.status_code == 200
              and (await c.get(avatar)).status_code == 404
              and (await c.get(r.json()["data"]["profile_picture_url"])).headers["Content-Type"] == "image/webp")
        replacements = await asyncio.gather(*(
            c.patch("/api/auth/me", headers=H, files=[("profile_picture", image)])
            for image in (IMG, IMG2)
        ))
        current_avatar = (await c.get("/api/auth/me", headers=H)).json()["data"]["profile_picture_url"]
        profiles = storage.parent / "profiles"
        check("concurrent avatar replacements leave only the current file",
              all(result.status_code == 200 for result in replacements)
              and {path.name for path in profiles.iterdir()} == {Path(current_avatar).name})
        r = await c.patch("/api/auth/me", headers=H, data={"location_id": "999999"})
        check("profile bad location 404", r.status_code == 404)
        r = await c.post("/api/auth/change-password", headers=H, json={
            "current_password": "nope1234", "new_password": "newpass123"})
        check("wrong current password 400", r.status_code == 400)
        r = await c.post("/api/auth/change-password", headers=H, json={
            "current_password": "pass1234", "new_password": "newpass123", "confirm_new_password": "different1"})
        check("explicit password confirmation still validated", r.status_code == 400)
        r = await c.post("/api/auth/login", json={"email": "test@example.com", "password": "pass1234"})
        other_device = r.json()["data"]
        changed, refreshed = await asyncio.gather(
            c.post("/api/auth/change-password", headers=H, json={
                "current_password": "pass1234", "new_password": "newpass123"}),
            c.post("/api/auth/refresh", json={"refresh_token": other_device["refresh_token"]}),
        )
        check("mobile password change without confirmation 204", changed.status_code == 204)
        check("refresh racing password change either rotates or is revoked",
              refreshed.status_code in (200, 401))
        if refreshed.status_code == 200:
            other_device = refreshed.json()["data"]
        other_device_headers = {"Authorization": f"Bearer {other_device['access_token']}"}
        for refresh, headers in ((rotated_refresh, H), (other_device["refresh_token"], other_device_headers)):
            r = await c.post("/api/auth/refresh", json={"refresh_token": refresh})
            check("password change revokes refresh on every device", r.status_code == 401)
            r = await c.get("/api/auth/me", headers=headers)
            check("password change revokes bearer access on every device", r.status_code == 401)
        r = await c.get("/api/auth/me", headers=H2)
        check("password change preserves sessions for other accounts", r.status_code == 200)
        r = await c.post("/api/auth/login", json={"email": "test@example.com", "password": "newpass123"})
        check("login with new password 200", r.status_code == 200)
        H = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

        # --- kyc (area chain validated against live Nepal data) ---
        provs = (await c.get("/api/nepal/provinces")).json()
        prov = next(p for p in provs if p["name"] == "बागमती प्रदेश")
        dists = (await c.get(f"/api/nepal/provinces/{prov['id']}/districts")).json()
        dist = next(d for d in dists if d["name"] == "ललितपुर")
        lvls = (await c.get(f"/api/nepal/districts/{dist['id']}/local")).json()
        lvl = next(l for l in lvls if str(l["id"]) == level_id)
        area = jsonlib.dumps({"id": lvl["id"], "name": lvl["name"]})
        prov_j = jsonlib.dumps({"id": prov["id"], "name": prov["name"]})
        dist_j = jsonlib.dumps({"id": dist["id"], "name": dist["name"]})
        kyc_files = [("selfiePhoto", IMG), ("documentFrontPhoto", IMG2), ("documentBackPhoto", IMG)]
        kyc_data = {"fullName": "Test User", "citizenshipNumber": "12-34-56-78901",
                    "gender": "other", "dateOfBirth": "1990-01-01",
                    "issuedDate": "2010-01-01", "wardNumber": "5",
                    "province": prov_j, "district": dist_j, "municipality": area}
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data,
                         files=[kyc_files[0], ("documentFrontPhoto", fake_jpeg), kyc_files[2]])
        check("invalid KYC image receives a document field error", r.status_code == 400
              and r.json()["detail"][0]["loc"] == ["body", "documentFrontPhoto"])
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data, files=kyc_files)
        check("kyc submit 201 pending", r.status_code == 201 and r.json()["data"]["status"] == "pending")
        check("kyc returns Other and January 1 calendar dates",
              (r.json()["data"]["gender"], r.json()["data"]["date_of_birth"],
               r.json()["data"]["issued_date"]) == ("other", "1990-01-01", "2010-01-01"))
        check("kyc exposes links not paths", "documents" in r.json()["data"]
              and "selfie_path" not in r.json()["data"])
        for field, value in [
            ("wardNumber", "ABC"),
            ("wardNumber", "0"),
            ("wardNumber", "2.5"),
            ("municipality", "[1,2]"),
            ("municipality", jsonlib.dumps({"name": lvl["name"]})),
            ("municipality", jsonlib.dumps({"id": 999999, "name": lvl["name"]})),
            ("municipality", jsonlib.dumps({"id": True, "name": lvl["name"]})),
            ("district", jsonlib.dumps({"id": dist["id"], "name": "Wrong District"})),
            ("district", jsonlib.dumps({"id": dist["id"] + 1, "name": dist["name"]})),
            ("province", jsonlib.dumps({"id": prov["id"] + 1, "name": prov["name"]})),
            ("dateOfBirth", "1990-02-30"),
            ("dateOfBirth", "1989-12-31T18:15:00.000Z"),
            ("issuedDate", "1989-12-31"),
            ("issuedDate", "9999-12-31"),
        ]:
            r = await c.post("/api/kyc/submit", headers=H2, data={**kyc_data, field: value}, files=kyc_files)
            check(f"invalid KYC {field} {value!r} returns a field error",
                  r.status_code == 400 and r.json()["detail"][0]["loc"] == ["body", field])
        r = await c.post("/api/kyc/submit", headers=H2, data={**kyc_data, "gender": "others"}, files=kyc_files)
        check("gender outside the shared enum returns a field error",
              r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "gender"])
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data, files=kyc_files)
        check("resubmit while pending 409", r.status_code == 409)
        r = await c.get("/api/kyc/me", headers=H)
        check("kyc me returns both January 1 dates", r.status_code == 200
              and r.json()["data"]["date_of_birth"] == "1990-01-01"
              and r.json()["data"]["issued_date"] == "2010-01-01")
        async with engine.begin() as conn:
            raw_dates = text('SELECT date_of_birth, issued_date FROM "KycSubmissions"')
            check("kyc stores only calendar dates",
                  (await conn.execute(raw_dates)).one() == ("1990-01-01", "2010-01-01"))
            await conn.execute(text(
                'UPDATE "KycSubmissions" SET date_of_birth = :dob, issued_date = :issued'
            ), {"dob": "1989-12-31 18:15:00.000000", "issued": "2010-01-01 00:00:00.000000"})
        for _ in range(2):
            await run_startup_migrations(engine)
        r = await c.get("/api/kyc/me", headers=H)
        check("kyc migration recovers Kathmandu dates and is idempotent", r.status_code == 200
              and r.json()["data"]["date_of_birth"] == "1990-01-01"
              and r.json()["data"]["issued_date"] == "2010-01-01")
        legacy_front = storage_config.save_local(IMG2[1], "kyc", "image/jpeg")
        async with engine.begin() as conn:
            await conn.execute(text('DELETE FROM "KycDocuments" WHERE kind = :kind'), {"kind": "front"})
            await conn.execute(text('UPDATE "KycSubmissions" SET doc_front_path = :filename'),
                               {"filename": legacy_front})
        async with Session() as session:
            await import_legacy_kyc_documents(session)
            await import_legacy_kyc_documents(session)
        with patch.object(storage_config, "STORAGE_DIR", Path(TMP) / "new-api-host"):
            r = await c.get("/api/kyc/documents/front", headers=H)
            check("legacy KYC import uses the real image type and keeps it available without the original disk",
                  r.status_code == 200 and r.content == IMG2[1] and r.headers["Content-Type"] == "image/png")
        r = await c.get("/api/kyc/documents/selfie", headers=H)
        check("owner doc 200 image", r.status_code == 200)
        r = await c.get("/api/kyc/documents/selfie", headers=H2, params={"user_id": owner_id})
        check("other user doc 403", r.status_code == 403)
        r = await c.get("/api/kyc/documents/nope", headers=H)
        check("bad doc 404", r.status_code == 404)

        # --- admin ---
        r = await c.get("/api/admin/issues/overview")
        check("admin without credentials 401", r.status_code == 401)
        r = await c.get("/api/admin/issues/overview", headers=AH)
        check("overview 200", r.status_code == 200 and r.json()["data"]["total_issues"] == 1)
        r = await c.get("/api/admin/issues", headers=AH, params={"search": "updated title"})
        check("main admin issue search retains reporter and filters", r.status_code == 200
              and r.json()["data"]["issues"][0]["reporter"]["id"] == owner_id)
        r = await c.get(f"/api/admin/subscribers/{owner_id}", headers=AH)
        check("main subscriber detail resolves a live local level", r.status_code == 200
              and r.json()["data"]["location"] == {"id": level_id, "name": home.name})
        r = await c.post(f"/api/admin/issues/{iid}/moderation", headers=AH, json={"category_id": new_cat})
        check("main moderation can assign an active category", r.status_code == 200)
        r = await c.delete(f"/api/category/{new_cat}", headers=AH)
        check("admin can retire a category", r.status_code == 200)
        r = await c.get("/api/issues/categories")
        check("retired category hidden from the picker", all(row["id"] != new_cat for row in r.json()["data"]))
        r = await c.get(f"/api/issues/{iid}", headers=H)
        check("retiring category preserves issue history", r.json()["data"]["category"]["id"] == new_cat)
        r = await c.patch(f"/api/admin/issues/{iid}/status", headers=AH, json={"status": "in_progress"})
        check("status open->in_progress 200", r.status_code == 200
              and r.json()["data"]["status"] == "in_progress")
        r = await c.get("/api/notifications", headers=H)
        check("owner notified of status", any(n["type"] == "status" for n in r.json()["data"]["notifications"]))
        r = await c.get(f"/api/admin/issues/{iid}/moderation", headers=AH)
        check("status endpoint writes moderation audit history", r.status_code == 200
              and any(change["field"] == "status" for event in r.json()["data"] for change in event["changes"]))
        r = await c.get("/api/admin/kyc", headers=AH)
        check("admin kyc list 1 pending", r.status_code == 200
              and r.json()["data"]["meta"]["total"] == 1)
        sub_id = r.json()["data"]["submissions"][0]["id"]
        r = await c.patch(f"/api/admin/kyc/{sub_id}", headers=AH,
                          json={"status": "approved", "note": "looks good"})
        check("kyc approve 200", r.status_code == 200 and r.json()["data"]["status"] == "approved")
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data, files=kyc_files)
        check("resubmit while approved 409", r.status_code == 409)
        r = await c.patch(f"/api/admin/kyc/{sub_id}", headers=AH,
                          json={"status": "rejected", "note": "blurry photo"})
        check("kyc reject 200", r.status_code == 200)
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data,
                         files=[kyc_files[0], ("documentFrontPhoto", fake_jpeg), kyc_files[2]])
        check("broken KYC resubmission keeps the previous document", r.status_code == 400
              and (await c.get("/api/kyc/documents/front", headers=H)).content == IMG2[1])
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data,
                         files=[kyc_files[0], ("documentFrontPhoto", webp), kyc_files[2]])
        check("resubmit after rejection 201", r.status_code == 201)
        await engine.dispose()
        with patch.object(storage_config, "STORAGE_DIR", Path(TMP) / "new-api-host"):
            async with app_module.app.router.lifespan_context(app_module.app):
                r = await c.get("/api/kyc/documents/front", headers=H)
                check("replacement KYC doc survives restart on an API host without the original disk",
                      r.status_code == 200 and r.content == webp[1]
                      and r.headers["Content-Type"] == "image/webp"
                      and r.headers["Cache-Control"] == "private, no-store")
        r = await c.get("/api/kyc/documents/selfie", headers=AH, params={"user_id": owner_id})
        check("admin reads owner doc 200", r.status_code == 200)
        async with httpx.AsyncClient(transport=transport, base_url="https://t") as portal:
            origin = {"Origin": os.environ["ADMIN_WEB_ORIGIN"]}
            r = await portal.post("/api/auth/admin/login", json=admin_login, headers=origin)
            check("main admin cookie login 204", r.status_code == 204)
            r = await portal.post("/api/category/seed")
            check("cookie-authenticated category write requires portal origin", r.status_code == 403)
            r = await portal.post("/api/category/seed", headers=origin)
            check("portal cookie can seed categories", r.status_code == 201)
            r = await portal.get("/api/kyc/documents/selfie", params={"user_id": owner_id})
            check("portal cookie can read authorized document", r.status_code == 200
                  and r.headers["Cache-Control"] == "private, no-store")
            async with Session() as s:
                await replace_password(s, await s.get(User, admin_id), hash_password("reset1234"))
            r = await portal.get("/api/auth/admin/me")
            check("password replacement revokes portal cookie sessions", r.status_code == 401)
            r = await c.get("/api/auth/me", headers=AH)
            check("password replacement also revokes bearer sessions", r.status_code == 401)
        r = await c.delete("/api/notifications", headers=H)
        check("clear-all 200", r.status_code == 200)
        r = await c.get("/api/notifications", headers=H)
        check("cleared empty", r.json()["data"]["meta"]["total"] == 0)

        # --- delete closes flow ---
        r = await c.delete(f"/api/issues/{iid}", headers=H, params={"delete_reason": "fixed"})
        check("delete non-open issue 400", r.status_code == 400)
        r = await c.post("/api/issues/create", headers=H, data={**report_data, "title": "Disposable open issue"}, files=files)
        iid2 = r.json()["data"]["id"]
        deleted_photo = r.json()["data"]["media"][0]["url"]
        r = await c.delete(f"/api/issues/{iid2}", headers=H, params={"delete_reason": "fixed"})
        check("owner delete 200", r.status_code == 200)
        r = await c.get(f"/api/issues/{iid2}", headers=H)
        check("deleted detail 404", r.status_code == 404)
        check("deleted report photo 404", (await c.get(deleted_photo)).status_code == 404)
        check("deleted report photo removed from disk", not (storage / Path(deleted_photo).name).exists())

        async with Session() as s:
            user = await s.get(User, owner_id)
            s.add(User(email="Test@example.com", name="Legacy User", password=user.password))
            await s.commit()
        r = await c.post("/api/auth/login", json={"email": "test@example.com", "password": "newpass123"})
        check("legacy email case variants preserve exact login", r.status_code == 200
              and r.json()["data"]["user_id"] == owner_id)
        r = await c.post("/api/auth/login", json={"email": "TEST@example.com", "password": "newpass123"})
        check("ambiguous legacy email case returns 401", r.status_code == 401)

        await check_hosted_photos(c, H, report_data, IMG, Session)

    await run_startup_migrations(engine)
    async with Session() as s:
        legacy = Issue(citizen_id=owner_id, category_id=cat_id, title="Legacy pin",
                       latitude=27.710, longitude=85.324, address="Saved address")
        unmatched = Issue(citizen_id=owner_id, category_id=cat_id, title="Legacy outside pin",
                          latitude=0, longitude=0)
        s.add_all([legacy, unmatched])
        await s.commit()
        await s.refresh(legacy)
        updated_at = legacy.updated_at
        await backfill_report_areas(s)
        await backfill_report_areas(s)
        for row in (legacy, unmatched):
            await s.refresh(row)
        check("migration uses legacy pin and preserves its coordinates, address and timestamp",
              (legacy.local_level_id, legacy.latitude, legacy.longitude, legacy.address, legacy.updated_at)
              == (report_level_id, 27.710, 85.324, "Saved address", updated_at))
        check("unmapped legacy pin stays unassigned", unmatched.local_level_id is None)
        issue = await s.get(Issue, iid)
        check("migration keeps report municipality and pin after residence change",
              (issue.local_level_id, issue.latitude, issue.longitude) == (level_id, 27.673, 85.324))

    await engine.dispose()
    print(f"\nALL {len(PASS)} CHECKS PASSED")


async def check_hosted_photos(client, headers, report_data, image, session_factory):
    from contextlib import suppress
    from datetime import timedelta
    from email.message import Message
    from io import BytesIO
    from unittest.mock import patch
    from urllib.parse import urlsplit

    from app.core import cloudinary, storage
    from app.models.models import Issue, IssueMedia, utcnow
    from app.models.photo_storage import PhotoObject
    from app.services import photo_storage

    assets = {}
    blocked = set()
    destroyed = []
    failures = []

    upload_count = 0

    def upload(payload, public_id, *, resource_type, type, overwrite, **_):
        nonlocal upload_count
        assert resource_type == "image" and type == "authenticated" and overwrite is False
        assets[public_id] = payload
        upload_count += 1
        if upload_count == 2:
            raise TimeoutError("Simulated lost upload response")
        return {"format": "jpg"}

    def destroy(key, *, type, resource_type, invalidate, **_):
        assert type in {"authenticated", "upload"} and resource_type == "image" and invalidate
        if key in blocked:
            failures.append(key)
            raise OSError("Simulated Cloudinary outage")
        destroyed.append((key, type))
        if key not in assets:
            return {"result": "not found"}
        del assets[key]
        return {"result": "ok"}

    def read(url, **_):
        parts = urlsplit(url).path.split("/")
        assert parts[1:4] == ["contract-test", "image", "authenticated"]
        assert parts[4].startswith("s--")
        key = "/".join(parts[-3:]).removesuffix(".jpg")
        response = BytesIO(assets[key])
        response.headers = Message()
        response.headers["Content-Type"] = "image/jpeg"
        return response

    async def wait_until(condition):
        async def poll():
            while not condition():
                await asyncio.sleep(0.01)

        await asyncio.wait_for(poll(), 2)

    config = cloudinary.cloudinary.config()
    with (
        patch.object(config, "cloud_name", "contract-test"),
        patch.object(config, "api_key", "fake"),
        patch.object(config, "api_secret", "fake"),
        patch.object(cloudinary.cloudinary.uploader, "upload", upload),
        patch.object(cloudinary.cloudinary.uploader, "destroy", destroy),
        patch.object(cloudinary, "urlopen", read),
        patch.object(photo_storage, "RETRY_DELAY", timedelta(milliseconds=30)),
    ):
        r = await client.post("/api/issues/create", headers=headers, data=report_data,
                              files=[("images", image), ("images", image)])
        check("partially uploaded hosted report leaves no remote objects", r.status_code == 500 and not assets)
        r = await client.post("/api/issues/create", headers=headers, data=report_data, files=[("images", image)])
        issue = r.json()["data"]
        photo_url = issue["media"][0]["url"]
        r = await client.get(photo_url)
        check("hosted photo is served through the API without caching", r.status_code == 200
              and r.headers["Cache-Control"] == "no-store" and r.content == image[1])

        key = next(iter(assets))
        blocked.add(key)
        r = await client.delete(f"/api/issues/{issue['id']}", headers=headers)
        check("hosted URL is revoked while physical cleanup is unavailable", r.status_code == 200
              and key in assets and (await client.get(photo_url)).status_code == 404)
        worker = asyncio.create_task(photo_storage.retry_photo_cleanup())
        try:
            await wait_until(lambda: key in failures)
            async with session_factory() as db:
                photo = await db.get(PhotoObject, photo_url)
                check("failed hosted deletion is durable", photo is not None and photo.delete_after is not None)
            blocked.clear()
            await wait_until(lambda: key not in assets)
            check("cleanup worker retries an unavailable hosted deletion", key not in assets)

            r = await client.patch("/api/auth/me", headers=headers, files=[("profile_picture", image)])
            previous_avatar = r.json()["data"]["profile_picture_url"]
            r = await client.patch("/api/auth/me", headers=headers, files=[("profile_picture", image)])
            check("replacing a hosted avatar revokes the previous URL",
                  r.status_code == 200 and (await client.get(previous_avatar)).status_code == 404)
            await wait_until(lambda: len(assets) == 1)
            check("the cleanup worker deletes the replaced hosted avatar", len(assets) == 1)
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

        legacy_name = storage.save_local(image[1], "issues", image[2])
        legacy_key = "merosamasya/owner/report/legacy"
        assets[legacy_key] = image[1]
        legacy_local = f"/api/files/issues/{legacy_name}"
        legacy_hosted = f"https://res.cloudinary.com/contract-test/image/upload/v1/{legacy_key}.jpg"
        async with session_factory.begin() as db:
            db.add(Issue(title="Previously deleted report", latitude=0, longitude=0, deleted_at=utcnow(),
                         media=[IssueMedia(url=legacy_local), IssueMedia(url=legacy_hosted)]))
        check("legacy deleted local photo is unavailable before cleanup", (await client.get(legacy_local)).status_code == 404)
        async with session_factory() as db:
            await photo_storage.retire_deleted_report_photos(db)
        for url in (legacy_local, legacy_hosted):
            await photo_storage.clean_photo(url)
        check("existing deleted reports queue legacy local and hosted photos for cleanup",
              not storage.stored_path("issues", legacy_name).exists() and (legacy_key, "upload") in destroyed)


asyncio.run(main())
