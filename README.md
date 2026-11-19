# Mero Samasya backend

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

## JWT refresh and logout

`POST /api/auth/refresh` consumes the submitted refresh token and returns
a new access and refresh token pair. Reusing a consumed or revoked token
returns 401 for an active account.

`POST /api/auth/logout` accepts `{"refresh_token": "..."}` and returns 204
after revoking that refresh token. Repeating logout with the same signed,
unexpired token is safe. Other logins remain active. Existing access tokens
remain usable until expiry, subject to the account-status check.

The app creates the `RefreshTokens` table on startup. Refresh tokens issued
before this change require a fresh login. Logout and refresh share the same
stored token record, so a token can only be consumed once.
