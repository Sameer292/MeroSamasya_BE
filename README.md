# Mero Samasya backend
FastAPI backend for the MeroSamasya citizen grievance app: auth, categories,
issues with photos, upvotes, profile, KYC, notifications, Nepal location data,
file serving, and admin reporting/status endpoints.

## Issue references

Display the full issue UUID from the API's `id` field as the issue reference.
Use the same value in issue URLs and when sharing or looking up an issue.
The web detail view already displays `issue.id`, and the numeric
`issueNumber` field is used only in mock data. The API uses a single identifier,
so existing issues need no backfill.

## Admin authentication

The web admin portal uses `/api/auth/admin/login`, `/api/auth/admin/me`,
and `/api/auth/admin/logout`. Set `ADMIN_WEB_ORIGIN`
to the browser-facing portal origin and keep `ADMIN_COOKIE_SECURE=true` on HTTPS.
Set it to `false` for local HTTP development.

Public registration creates citizen accounts. The `data.role` field on
`GET /api/auth/me` reports `citizen`, `admin`, or `superadmin` from the
account's current membership. Existing admin grants continue to apply.

The app creates the `AdminMemberships` and `AdminSessions` tables on startup.
To provision an administrator, have them register, verify the intended
account's email, and grant membership using an authorized database connection.
Replace the example email with the verified account and confirm one row was
inserted.

```sql
INSERT INTO "AdminMemberships" (user_id, role)
SELECT id, 'admin' FROM "Users" WHERE email = 'admin@example.com';
```

Remove the membership to revoke admin access on subsequent requests. Delete
the account's rows in `AdminSessions` as part of revocation to invalidate its
session cookies if the account is later promoted again.

Protected admin endpoints accept the portal's session cookie or an access
token as a bearer credential. Requests without valid credentials receive
401. Authenticated citizens receive 403. Inactive and suspended accounts
receive 403 on login, authenticated requests, and token refresh. Missing
and deleted accounts receive 401. The check uses the current database status
on each request, so it also applies to credentials issued before a status change.
Reactivation restores access for credentials that are still valid.

`POST /api/auth/admin/logout` requires an active administrator and the
configured portal origin. It revokes the presented portal session cookie and
clears it from the browser. Portal sessions have no server-side timeout.
Bearer-token clients use the JWT logout endpoint below.

## Admin issue reads

`GET /api/admin/issues` and `GET /api/admin/issues/{issue_id}` require an
active admin or superadmin. Both endpoints exclude soft-deleted issues. The
detail endpoint returns 404 for a missing or soft-deleted issue. Each issue
includes a `reporter` with only `id` and `name`, or `null` when no reporter
is associated with it.

The list accepts these query parameters.

| Parameter | Behavior |
| --- | --- |
| `search` | Case-insensitive substring match across title, description, and address. Blank values are ignored. |
| `status` | Exact match on `open`, `in_progress`, `resolved`, or `closed`. |
| `category_id` | Exact match on the category ID. |
| `sort` | `newest` (default) or `oldest`, ordered by creation time with issue ID breaking ties. |
| `page` | One-based page number. Defaults to 1. |
| `limit` | Page size from 1 to 100. Defaults to 10. |

Search and filters combine. The response contains `data.issues` and
`data.meta` with `total`, `page`, `limit`, and `total_pages`. Totals reflect
the matching issues even when the requested page is empty.

## JWT refresh and logout

`POST /api/auth/refresh` consumes the submitted refresh token and returns
a new access and refresh token pair for the same session. Reusing a consumed
or revoked token returns 401 for an active account.

`POST /api/auth/logout` accepts `{"refresh_token": "..."}` and returns 204
after revoking that login session. A signed refresh token can revoke its
session even after rotation or expiry. Revocation invalidates both bearer
access and refresh. Other logins remain active.

Password changes revoke all bearer and portal sessions for the account.
Password replacement after a verified reset uses the same transaction.

On upgrade, older access tokens return 401 so clients refresh once to
establish the session ID. Existing tracked refresh tokens can rotate as usual.

## Local run (SQLite, no extra services)

Use a command-line database override to run against local SQLite.

```bash
DATABASE_URL="sqlite+aiosqlite:///./local.db" \
JWT_SECRET="dev-secret-at-least-32-chars-long-please" \
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

First boot creates the schema, runs idempotent migrations, seeds the 9 bundled
categories when empty, and reconciles the bundled Nepal location data
(7 provinces, 77 districts, 753 local levels). To force a clean geo reseed,
delete the SQLite file and reboot.

## Environment

See `.env.example` for the full list. Notes:

- `DATABASE_URL` — `sqlite+aiosqlite:///./file.db` locally,
  `postgresql+asyncpg://...` for shared deployments.
- `JWT_SECRET` — required, HMAC key (32+ chars). The app refuses to boot
  without it.
- `CLOUDINARY_*` — optional. When set, issue photos and avatars upload to
  Cloudinary as authenticated assets. When unset, they use `LOCAL_STORAGE_DIR`
  (default `./storage`, gitignored). The API serves both, revokes retired URLs,
  and retries storage deletions from the database while the app is running.
- KYC identity documents are **always** stored locally and served only
  through the authorized `GET /api/kyc/documents/{doc}` endpoint, never
  through public URLs.

## Checks

```bash
.venv/bin/python tests/checks.py
```

Runs the whole citizen flow (auth, categories, issues, votes, media retain,
profile, password, KYC, notifications, admin) against a temp SQLite DB with
local storage. No network, no Cloudinary.

## Data sources

- Nepal province/district/local-level data (`app/data/nepal_locations.json`,
  7 provinces, 77 districts, 753 local levels, official Nepali names):
  https://mofaga.gov.np/local-contact?visible=753

## Mobile contract

See `API_CONTRACT.md` for the exact endpoint/field contract the mobile app
is built against.
