# Mero Samasya backend

## Admin authentication

The web admin portal uses `/api/auth/admin/login`, `/api/auth/admin/me`,
`/api/auth/admin/refresh`, and `/api/auth/admin/logout`. Set `ADMIN_WEB_ORIGIN`
to the browser-facing portal origin and keep `ADMIN_COOKIE_SECURE=true` on HTTPS.
Set it to `false` for local HTTP development.

The app creates the `AdminMemberships` and `AdminSessions` tables on startup.
After the user has registered, grant admin access with an authorized database
connection. Replace the example email with the intended account.

```sql
INSERT INTO "AdminMemberships" (user_id, role)
SELECT id, 'admin' FROM "Users" WHERE email = 'admin@example.com';
```

Remove the membership to deny future portal requests. An admin browser session
has a fixed lifetime set by `REFRESH_TOKEN_EXPIRY_DAYS`. Refresh extends its
access window within that lifetime using `ACCESS_TOKEN_EXPIRE_MINUTES`.
Logout revokes the session in the database.
