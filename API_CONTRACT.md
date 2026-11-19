# MeroSamasya Backend — Mobile API Contract

Base URL (local): `http://<host>:8000`. Authenticated requests send
`Authorization: Bearer <access_token>`. Admin endpoints require an active
admin or superadmin with a bearer access token or the portal session cookie.
Cookie-authenticated admin writes require the configured portal origin.

## Auth (`/api/auth`)

| Method | Path | Auth | Body | Response `data` |
|---|---|---|---|---|
| POST | `/api/auth/register` | no | `{name, phone (10 digits), email, password (8+ chars, letter+number), confirm_password}` | `{user_id}` (201) |
| POST | `/api/auth/login` | no | `{email, password}` (email case-insensitive) | `{access_token, refresh_token, user_id}` |
| POST | `/api/auth/refresh` | no | `{refresh_token}` (must be a refresh token; access tokens 401) | `{access_token, refresh_token, user_id}` (rotated) |
| GET | `/api/auth/me` | Bearer | — | `UserData` (see below) |
| PATCH | `/api/auth/me` | Bearer | multipart `{name?, phone?, location_id?, profile_picture?}` | `UserData` |
| POST | `/api/auth/change-password` | Bearer | `{current_password, new_password, confirm_new_password?}` (same strength rules; wrong current → 400) | 204 |
| POST | `/api/auth/logout` | no | `{refresh_token}` | 204 |

`UserData = {id, email, name, phone, location: {id: string, name} | null,
profile_picture_url, account_status, role, created_at, updated_at, deleted_at}`.
Inactive and suspended users receive 403. Missing and deleted accounts
receive 401. A consumed or revoked refresh token returns 401 for an active
account. Register and login normalize email to lowercase.

## Categories

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/category/` | no | `[{id, name, icon, color}]`; 9 defaults seeded on fresh boot |
| GET | `/api/issues/categories` | no | alias of the above (kept for compatibility) |
| POST / PATCH / DELETE | `/api/category/...` | admin | citizen clients must not call these |
| POST | `/api/category/seed` | admin | idempotent reseed of the 9 defaults |

## Issues (`/api/issues`, Bearer required)

`IssueData = {id, citizen_id, category, title, description?, status
(open|in_progress|resolved|closed), latitude, longitude, address?,
media: [{id, url, created_at}], upvote_count, has_upvoted, local_level_id?,
created_at, updated_at, resolved_at?}`. Media `url` is absolute (Cloudinary)
or app-relative (`/api/files/issues/<name>` — prepend the base URL).

| Method | Path | Body | Response `data` |
|---|---|---|---|
| POST | `/api/issues/create` | multipart: `category_id, title (3-200), description?, latitude, longitude, address?, local_level_id?` + 1–3 `images` (jpeg/png/webp, ≤5 MB each) | `IssueData` (201). Area = explicit `local_level_id` or reporter's area snapshot |
| GET | `/api/issues/all?page&limit` | — | `{meta: {total, page, limit, total_pages}, issues}` (page≥1, limit 1–100) |
| GET | `/api/issues/me?...` | — | same shape, own non-deleted issues |
| GET | `/api/issues/nearme?...` | — | same shape, issues whose area = caller's area (400 if caller has none) |
| GET | `/api/issues/{id}` | — | `IssueData` |
| PATCH | `/api/issues/{id}` | multipart: any of `category_id?, title?, description?, latitude?, longitude?, address?, local_level_id?`, `retained_media_ids?`, new `images?` | `IssueData`. Only `open` issues, owner only |
| DELETE | `/api/issues/{id}?delete_reason=` | — | `{id}`. Only `open` issues, owner only |
| POST | `/api/issues/{id}/upvote` | — | `{upvoted: bool, upvote_count: int}` (toggle; owner gets a notification except on self-votes) |

Photo edit rule: `retained_media_ids` is a **JSON string array** of existing
media ids to keep, e.g. `retained_media_ids: "[\"id1\",\"id2\"]"`. Omitted =
legacy behavior (new files replace all; no files touches nothing). Explicit
(including `[]`) = keep exactly those. Retained + new must total 1–3, else
400. Unknown ids → 400.

## Location (`/api/location`)

| Method | Path | Auth | Body | Response `data` |
|---|---|---|---|---|
| GET | `/api/location/locations?district_id=` | no | — | `[{id: string, name}]` from live local-level data (721+ rows); `id` is `String(local_levels.id)` |
| PATCH | `/api/location/location` | Bearer | `{location_id}` — must be an id from the list above | `UserData` |

## Nepal geo (`/api/nepal`, all GETs public)

`GET /provinces` → `[{id, name}]`; `GET /provinces/{id}/districts` →
`[{id, name}]`; `GET /districts/{id}/local[?local_level_type=]`
→ `[{id, name, type}]`. `POST /seed` is admin-only.

## KYC (`/api/kyc`, Bearer required)

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/kyc/submit` | multipart: `fullName, citizenshipNumber, gender (male/female/other), dateOfBirth (ISO), issuedDate (ISO), wardNumber, tole?, province/district/municipality (JSON `{id, name}` from this API), files `selfiePhoto, documentFrontPhoto, documentBackPhoto` (images, ≤5 MB) | 201 `{status: pending}`. Area id is verified against live geo data (400 on mismatch). Resubmit blocked while pending/approved (409); allowed after rejection |
| GET | `/api/kyc/me` | — | own submission + status; `documents: {selfie, front, back}` link paths, never file paths |
| GET | `/api/kyc/documents/{selfie\|front\|back}[?user_id=]` | — | Private file bytes. Citizens can read their own documents. Admins can read a submission for the specified user. |

Identity documents are stored on local disk only and never exposed as public
URLs. On resubmission, new files commit first and old files are deleted only
after the commit succeeds.

## Notifications (`/api/notifications`, Bearer required)

| Method | Path | Response |
|---|---|---|
| GET | `/api/notifications?page&limit` | `{notifications: [{id, type, title, message, read, created_at, issue_id?}], meta: {total, page, limit}, unread_count}` |
| PATCH | `/api/notifications/{id}/read` | `{id, read: true}` (owner only, else 404) |
| DELETE | `/api/notifications` | `{message}` (clears own list) |

Generated server-side: welcome on register, upvote on someone else's vote,
status changes, KYC decisions.

## Files (`/api/files`, public)

`GET /api/files/{issues|profiles}/{name}` serves locally stored uploads.
`kyc` is never servable here.

## Admin (`/api/admin`, admin or superadmin required)

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/admin/issues?page&limit&status&category_id&search&sort` | — | paginated results with reporter details and optional filters |
| GET | `/api/admin/issues/overview` | — | `{open, in_progress, resolved, closed, total_issues, total_users, kyc_pending}` |
| PATCH | `/api/admin/issues/{id}/status` | `{status}` | Applies the moderation transition policy (409 for an invalid transition), records the change and notifies the owner |
| GET | `/api/admin/kyc?page&limit&status` | — | submissions with status |
| PATCH | `/api/admin/kyc/{id}` | `{status: approved\|rejected, note?}` | notifies the user |

## Status codes

422 validation, 400 bad input/state, 401 missing or invalid credentials, 403
forbidden (incl. insufficient role or non-owner), 404 missing, 409 conflict
(duplicate register/category, KYC resubmit guard, seeded data), 500/503
server/unconfigured uploads.
