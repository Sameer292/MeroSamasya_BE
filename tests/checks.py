"""Runnable contract checks for the citizen grievance flow.

Runs the real app over ASGI against a temp SQLite DB with uploads on local
disk. No network, no Cloudinary, no pytest needed:
    .venv/bin/python tests/checks.py
"""

import asyncio
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="merosamasya-checks-")
os.environ["LOCAL_STORAGE_DIR"] = os.path.join(TMP, "storage")
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ.setdefault("JWT_SECRET", "test-secret")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(TMP, "checks.db")

PASS = []


def check(name, cond):
    assert cond, f"FAILED: {name}"
    PASS.append(name)
    print(f"ok: {name}")


async def main():
    import httpx
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    from app.core.database import Base, get_db
    from app.models import models  # noqa: F401
    from app.models import nepal_location_models  # noqa: F401
    from app.models.models import User
    from app.models.nepal_location_models import Province, District, LocalLevel
    from app.schemas.enum import LocalLevelType, AccountStatusEnum
    from app.services.category_service import ensure_default_categories
    import main as app_module

    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as s:
        await ensure_default_categories(s)
        prov = Province(name="Bagmati")
        s.add(prov)
        await s.flush()
        dist = District(name="Lalitpur", province_id=prov.id)
        s.add(dist)
        await s.flush()
        s.add(LocalLevel(name="Lalitpur Metro", type=LocalLevelType.MA_NA_PA, district_id=dist.id))
        await s.commit()
        level_id = (await s.execute(select(LocalLevel.id))).scalar_one()

    async def override_db():
        async with Session() as session:
            yield session

    app_module.app.dependency_overrides[get_db] = override_db

    transport = httpx.ASGITransport(app=app_module.app)
    IMG = ("p.jpg", b"\xff\xd8\xff" + b"x" * 100, "image/jpeg")
    IMG2 = ("q.png", b"\x89PNG" + b"y" * 100, "image/png")

    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        # --- auth ---
        r = await c.post("/api/auth/register", json={
            "name": "Test User", "phone": "9800000001", "email": "Test@Example.com",
            "password": "pass1234", "confirm_password": "pass1234"})
        check("register 201", r.status_code == 201)
        r = await c.post("/api/auth/register", json={
            "name": "Test User", "phone": "9800000001", "email": "test@example.com",
            "password": "pass1234", "confirm_password": "pass1234"})
        check("duplicate register 400", r.status_code == 400)
        r = await c.post("/api/auth/login", json={"email": "TEST@example.com", "password": "pass1234"})
        check("login normalizes case 200", r.status_code == 200)
        tokens = r.json()["data"]
        owner_id = tokens["user_id"]
        H = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = await c.post("/api/auth/login", json={"email": "test@example.com", "password": "wrongpass1"})
        check("wrong password 401", r.status_code == 401)
        r = await c.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        check("refresh 200", r.status_code == 200)
        r = await c.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
        check("access-as-refresh 401", r.status_code == 401)
        r = await c.post("/api/auth/refresh", json={"refresh_token": "garbage"})
        check("garbage refresh 401 not 500", r.status_code == 401)
        r = await c.get("/api/auth/me", headers=H)
        check("me 200, location null", r.status_code == 200 and r.json()["data"]["location"] is None)

        # suspended user blocked everywhere
        async with Session() as s:
            u = (await s.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
            u.account_status = AccountStatusEnum.suspended
            await s.commit()
        r = await c.get("/api/auth/me", headers=H)
        check("suspended /me 403", r.status_code == 403)
        r = await c.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        check("suspended refresh 401", r.status_code == 401)
        async with Session() as s:
            u = (await s.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
            u.account_status = AccountStatusEnum.active
            await s.commit()

        # --- categories ---
        r = await c.get("/api/issues/categories")
        check("mobile categories alias 200", r.status_code == 200 and len(r.json()["data"]) == 9)
        cat_id = r.json()["data"][0]["id"]
        r = await c.post("/api/category/", json={"name": "X", "icon": "i", "color": "#fff"})
        check("category write unauth 403", r.status_code == 403)
        AH = {"X-Admin-Key": "test-admin-key"}
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
              and r.json()["data"]["location"] == {"id": str(level_id), "name": "Lalitpur Metro"})
        r = await c.patch("/api/location/location", json={"location_id": "999999"}, headers=H)
        check("bad location 404", r.status_code == 404)

        # --- issues ---
        r = await c.get("/api/issues/all?page=0", headers=H)
        check("page=0 -> 422", r.status_code == 422)
        files = [("images", IMG)]
        r = await c.post("/api/issues/create", headers=H, data={
            "category_id": cat_id, "title": "Pothole on Main Road",
            "latitude": "27.7", "longitude": "85.3"}, files=files)
        check("create without desc/addr 201", r.status_code == 201)
        issue = r.json()["data"]
        check("area snapshotted from user", issue["local_level_id"] == str(level_id))
        check("local media url", issue["media"][0]["url"].startswith("/api/files/issues/"))
        r = await c.get(issue["media"][0]["url"])
        check("stored photo served 200", r.status_code == 200)
        iid = issue["id"]
        mid = issue["media"][0]["id"]
        r = await c.post("/api/issues/create", headers=H, data={
            "category_id": "nope", "title": "Bad cat issue",
            "latitude": "1", "longitude": "1"}, files=files)
        check("bad category 404", r.status_code == 404)
        r = await c.post("/api/issues/create", headers=H, data={
            "category_id": cat_id, "title": "No image issue",
            "latitude": "1", "longitude": "1"})
        check("no images 400", r.status_code == 400)
        r = await c.post("/api/issues/create", headers=H, data={
            "category_id": cat_id, "title": "Bad type issue",
            "latitude": "1", "longitude": "1"},
            files=[("images", ("t.txt", b"hi", "text/plain"))])
        check("bad file type 400", r.status_code == 400)

        for path in (f"/api/issues/{iid}", "/api/issues/me", "/api/issues/all", "/api/issues/nearme"):
            r = await c.get(path, headers=H, params={"page": 1, "limit": 10} if "{" not in path else None)
            check(f"read {path} 200", r.status_code == 200)
        r = await c.get("/api/issues/nearme", headers=H)
        check("nearme finds own-area issue", r.json()["data"]["meta"]["total"] == 1)

        # --- second user + votes ---
        r = await c.post("/api/auth/register", json={
            "name": "Voter Two", "phone": "9800000002", "email": "voter2@example.com",
            "password": "pass1234", "confirm_password": "pass1234"})
        r = await c.post("/api/auth/login", json={"email": "voter2@example.com", "password": "pass1234"})
        H2 = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
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
        r = await c.patch(f"/api/issues/{iid}", headers=H, data={"title": "Updated title here"},
                          files=[("images", IMG2)])
        check("edit replace-all legacy 200", r.status_code == 200 and len(r.json()["data"]["media"]) == 1)
        kept = r.json()["data"]["media"][0]["id"]
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps([kept])},
                          files=[("images", IMG), ("images", IMG2)])
        check("retain 1 + add 2 = 3", r.status_code == 200 and len(r.json()["data"]["media"]) == 3)
        r = await c.patch(f"/api/issues/{iid}", headers=H,
                          data={"retained_media_ids": jsonlib.dumps(["no-such-id"])},
                          files=[("images", IMG)])
        check("foreign keep id 400", r.status_code == 400)
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
        r = await c.patch("/api/auth/me", headers=H, data={
            "name": "Test Renamed", "phone": "9800000009", "location_id": str(level_id)},
            files=[("profile_picture", IMG)])
        check("profile update 200", r.status_code == 200
              and r.json()["data"]["name"] == "Test Renamed")
        r = await c.patch("/api/auth/me", headers=H, data={"location_id": "999999"})
        check("profile bad location 404", r.status_code == 404)
        r = await c.post("/api/auth/change-password", headers=H, json={
            "current_password": "nope1234", "new_password": "newpass123"})
        check("wrong current password 401", r.status_code == 401)
        r = await c.post("/api/auth/change-password", headers=H, json={
            "current_password": "pass1234", "new_password": "newpass123"})
        check("password change 200", r.status_code == 200)
        r = await c.post("/api/auth/login", json={"email": "test@example.com", "password": "newpass123"})
        check("login with new password 200", r.status_code == 200)

        # --- kyc (area chain validated against live Nepal data) ---
        import json as jsonlib2  # noqa: F401
        provs = (await c.get("/api/nepal/provinces")).json()
        prov = next(p for p in provs if p["name"] == "Bagmati")
        dists = (await c.get(f"/api/nepal/provinces/{prov['id']}/districts")).json()
        dist = next(d for d in dists if d["name"] == "Lalitpur")
        lvls = (await c.get(f"/api/nepal/districts/{dist['id']}/local")).json()
        lvl = next(l for l in lvls if l["id"] == level_id)
        area = jsonlib.dumps({"id": lvl["id"], "name": lvl["name"]})
        prov_j = jsonlib.dumps({"id": prov["id"], "name": prov["name"]})
        dist_j = jsonlib.dumps({"id": dist["id"], "name": dist["name"]})
        kyc_files = [("selfiePhoto", IMG), ("documentFrontPhoto", IMG2), ("documentBackPhoto", IMG)]
        kyc_data = {"fullName": "Test User", "citizenshipNumber": "12-34-56-78901",
                    "gender": "male", "dateOfBirth": "1990-01-01T00:00:00.000Z",
                    "issuedDate": "2010-05-05T00:00:00.000Z", "wardNumber": "5",
                    "province": prov_j, "district": dist_j, "municipality": area}
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data, files=kyc_files)
        check("kyc submit 201 pending", r.status_code == 201 and r.json()["data"]["status"] == "pending")
        check("kyc exposes links not paths", "documents" in r.json()["data"]
              and "selfie_path" not in r.json()["data"])
        bad = dict(kyc_data, district=jsonlib.dumps({"id": dist["id"], "name": "Wrong District"}))
        r = await c.post("/api/kyc/submit", headers=H2, data=bad, files=kyc_files)
        check("area mismatch 400", r.status_code == 400)
        bad2 = dict(kyc_data, municipality="[1,2]")
        # use voter2 (no submission yet) for payload-shape errors
        r = await c.post("/api/kyc/submit", headers=H2, data=bad2, files=kyc_files)
        check("non-object area 400", r.status_code == 400)
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data, files=kyc_files)
        check("resubmit while pending 409", r.status_code == 409)
        r = await c.get("/api/kyc/me", headers=H)
        check("kyc me 200", r.status_code == 200)
        r = await c.get("/api/kyc/documents/selfie", headers=H)
        check("owner doc 200 image", r.status_code == 200)
        r = await c.get("/api/kyc/documents/selfie", headers=H2, params={"user_id": owner_id})
        check("other user doc 403", r.status_code == 403)
        r = await c.get("/api/kyc/documents/nope", headers=H)
        check("bad doc 404", r.status_code == 404)

        # --- admin ---
        r = await c.get("/api/admin/issues/overview")
        check("admin no key 403", r.status_code == 403)
        r = await c.get("/api/admin/issues/overview", headers=AH)
        check("overview 200", r.status_code == 200 and r.json()["data"]["total_issues"] == 1)
        r = await c.patch(f"/api/admin/issues/{iid}/status", headers=AH, json={"status": "resolved"})
        check("invalid jump open->resolved 400", r.status_code == 400)
        r = await c.patch(f"/api/admin/issues/{iid}/status", headers=AH, json={"status": "in_progress"})
        check("status open->in_progress 200", r.status_code == 200
              and r.json()["data"]["status"] == "in_progress")
        r = await c.get("/api/notifications", headers=H)
        check("owner notified of status", any(n["type"] == "status" for n in r.json()["data"]["notifications"]))
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
        r = await c.post("/api/kyc/submit", headers=H, data=kyc_data, files=kyc_files)
        check("resubmit after rejection 201", r.status_code == 201)
        kyc_dir = os.path.join(os.environ["LOCAL_STORAGE_DIR"], "kyc")
        check("old docs replaced, 3 files", len(os.listdir(kyc_dir)) == 3)
        r = await c.get("/api/kyc/documents/front", headers=H)
        check("new doc served 200", r.status_code == 200)
        r = await c.get("/api/kyc/documents/selfie", headers={**H, **AH}, params={"user_id": owner_id})
        check("admin reads owner doc 200", r.status_code == 200)
        r = await c.delete("/api/notifications", headers=H)
        check("clear-all 200", r.status_code == 200)
        r = await c.get("/api/notifications", headers=H)
        check("cleared empty", r.json()["data"]["meta"]["total"] == 0)

        # --- delete closes flow ---
        r = await c.delete(f"/api/issues/{iid}", headers=H, params={"delete_reason": "fixed"})
        check("delete non-open issue 400", r.status_code == 400)
        r = await c.post("/api/issues/create", headers=H, data={
            "category_id": cat_id, "title": "Disposable open issue",
            "latitude": "1", "longitude": "1"}, files=files)
        iid2 = r.json()["data"]["id"]
        r = await c.delete(f"/api/issues/{iid2}", headers=H, params={"delete_reason": "fixed"})
        check("owner delete 200", r.status_code == 200)
        r = await c.get(f"/api/issues/{iid2}", headers=H)
        check("deleted detail 404", r.status_code == 404)

    await engine.dispose()
    print(f"\nALL {len(PASS)} CHECKS PASSED")


asyncio.run(main())
