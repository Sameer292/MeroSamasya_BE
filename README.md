# Mero Samasya backend

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
401. Authenticated citizens receive 403. Admin sessions have no server-side
timeout. Logout revokes the session in the database. The browser may clear
its cookie when it closes. Sign in again once after upgrading from the
earlier expiring-session implementation.
