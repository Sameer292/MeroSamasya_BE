# MeroSamasya Backend — Mobile API Contract

Base URL (local): `http://<host>:8000`. Authenticated requests send
`Authorization: Bearer <access_token>`. Admin endpoints require an active
admin or superadmin with a bearer access token or the portal session cookie.
Cookie-authenticated admin writes require the configured portal origin.

Report photos, profile avatars, and KYC documents accept still JPEG, PNG,
and WebP files up to 5 MiB, 8192 pixels on either side, and 24 megapixels.
The API verifies the image bytes and uses the detected format. Invalid images
return a 400 with a field error. Report photo errors include the upload index.

## Auth (`/api/auth`)

| Method | Path | Auth | Body | Response `data` |
|---|---|---|---|---|
| POST | `/api/auth/register` | no | `{name, phone (10 digits), email, password (8+ chars, letter+number), confirm_password}` | `{user_id}` (201) |
| POST | `/api/auth/login` | no | `{email, password}` (email case-insensitive) | `{access_token, refresh_token, user_id}` |
| POST | `/api/auth/refresh` | no | `{refresh_token}` (must be a refresh token; access tokens 401) | `{access_token, refresh_token, user_id}` (rotated) |
| GET | `/api/auth/me` | Bearer | — | `UserData` (see below) |
| PATCH | `/api/auth/me` | Bearer | multipart `{name?, phone?, location_id?, profile_picture?}` | `UserData` |
| DELETE | `/api/auth/me` | Bearer, citizen only | JSON `{current_password}` (required; incorrect → 400) | 204, account deleted and all sessions revoked |
| POST | `/api/auth/change-password` | Bearer | `{current_password, new_password, confirm_new_password?}` (same strength rules; wrong current → 400) | 204, all of the account's sessions revoked |
| POST | `/api/auth/logout` | no | `{refresh_token}` | 204, the submitted token's session revoked |

`UserData = {id, email, name, phone, location: {id: string, name} | null,
profile_picture_url, account_status, role, created_at, updated_at, deleted_at}`.
Inactive and suspended users receive 403. Missing and deleted accounts
receive 401. Revoked sessions return 401 on bearer requests and refresh.
Refresh tokens can be rotated once. Register and login normalize email to
lowercase.

### Citizen privacy and deletion retention policy

Report text and exact pins are visible to signed-in citizens and administrators
for finding and resolving civic issues. Report photos and avatars are accessible
to anyone with their URL. Identity details, citizenship document images, and
selfies are collected for identity verification and review, accessible only to
the owner and authorized administrators, and kept while the account exists.
KYC is optional for posting reports. Mobile explains this before submission.

Account deletion requires an active bearer session and the current password in
the same request. It is permanent; this endpoint cannot delete administrator
accounts. A single transaction:

- Removes KYC submissions, document bytes, citizenship details, addresses,
  dates of birth, reviewer notes, notifications, and the citizen's upvotes.
- Scrubs name, email, phone, residence, avatar, and password. Only the account
  UUID, timestamps, deleted status, a synthetic email, and a random password hash
  remain as a tombstone; the original email can be registered again.
- Revokes every refresh/access session and any portal session for the account.
  Access tokens are checked against live sessions on each authenticated request.
- Clears `citizen_id` and the submission retry ID on all civic reports, including
  previously deleted reports. Civic report text, photos, exact pins, municipality,
  status, timestamps, and moderation history remain for civic accountability,
  without an account link. There is no automatic expiry for retained civic records.
  Personal details a citizen placed in report text or photos are **not** automatically
  redacted. The deletion notice states this and that report management is lost.
- Retires the avatar and queues legacy local identity files for deletion. API
  photo URLs and all KYC document endpoints immediately lose access. Physical
  cleanup uses the durable `PhotoObjects` queue;
  the worker retries failures every 30 seconds, including after server restarts.
  Cloudinary cleanup also invalidates cached copies. Legacy public Cloudinary
  URLs remain accessible until that cleanup succeeds. Already downloaded copies
  cannot be recalled.

Citizen profile, KYC, report, and vote writes recheck and lock the active account
before persisting, so requests authenticated before deletion cannot recreate data.
Failures before commit roll back deletion. On confirmed 204, mobile clears this
account's saved draft and draft photos, in-memory report form, query cache, and
secure session on the current device. Other devices lose server access; their
offline drafts cannot be remotely erased. Local cleanup failures are surfaced
with instructions to clear app storage.

This policy governs the live application database and managed file storage.
Infrastructure backups and external copies are not managed by this API. Operators
must apply their backup expiry controls and reapply account deletions before
restoring a backup to service; restoring an old database must not restore access
to deleted accounts or identity documents.

Signup and profile updates trim names and require 2–50 characters using
Unicode letters, combining marks, and spaces. Request validation returns
HTTP 422 with `{"detail":[{"loc":["body","name"],"msg":"…","type":"…"}]}`.

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
created_at, updated_at, resolved_at?}`. New photo URLs are app-relative
(`/api/files/issues/<name>`). Older Cloudinary URLs can be absolute.

| Method | Path | Body | Response `data` |
|---|---|---|---|
| POST | `/api/issues/create` | multipart: `submission_id` (UUID v4), `category_id, title (3-200), description?, latitude, longitude, address?, local_level_id` + 1–3 `images` (jpeg/png/webp, ≤5 MB each) | `IssueData` (201) |
| GET | `/api/issues/all?page&limit` | — | `{meta: {total, page, limit, total_pages}, status_counts, issues}` (page≥1, limit 1–100) |
| GET | `/api/issues/me?...` | — | same shape, own non-deleted issues |
| GET | `/api/issues/nearme?...` | — | same shape, issues whose area = caller's area (400 if caller has none) |
| GET | `/api/issues/{id}` | — | `IssueData` plus `status_updates: [{status, created_at}]` |
| PATCH | `/api/issues/{id}` | multipart: `category_id?, title?, description?, address?, retained_media_ids?`, new `images?`, and the optional pin triplet (`latitude`, `longitude`, `local_level_id`) | `IssueData`. Only `open` issues, owner only |
| DELETE | `/api/issues/{id}?delete_reason=` | — | `{id}`. Only `open` issues, owner only |
| POST | `/api/issues/{id}/upvote` | JSON `{"upvoted": true}` to add or `{"upvoted": false}` to remove | `{upvoted: bool, upvote_count: int}`. A new vote from another account notifies the owner. |

Detail status updates start with `open` at submission, followed by recorded
status changes in chronological order, including reopening. Dates include a
timezone. Category changes, reviewer IDs and internal moderation fields are
excluded. Older changes made before moderation history was recorded cannot
be reconstructed; the current `status` remains authoritative.

Citizen lists (`all`, `me`, and `nearme`) accept `search` (trimmed, at most
200 characters), `category_id`, and `status` (`open|in_progress|resolved|closed`).
Search matches a literal, case-insensitive substring in title, description,
address, or category name. All filters apply before pagination. `meta.total`
and `total_pages` describe the fully matched set. `status_counts` contains
all four status totals for the same scope, search, and category, before the
status filter, so chips can show counts for switching status. Lists sort by
creation date descending, then ID descending for stable pagination. My Area
uses the report municipality, including legacy IDs for that municipality.

Generate a submission ID once per draft and reuse it on retries. For the
same authenticated account and submission ID, the first successful create
sets the report's contents. Retrying returns the original report ID with 201,
including after deletion. Repeating either upvote state leaves the vote
unchanged and adds no notification.

Create requests require a confirmed municipality ID. Pin edits send both
coordinates and the municipality ID together. The API checks that the pin is
inside or on the boundary of the selected municipality and saves the three
values together. Changing the reporter's residence has no effect on a report's
municipality. Existing reports keep their saved pins and municipality IDs.
Legacy pins with no area ID are assigned only when they match one municipality.

Latitude must be finite and within −90 to 90. Longitude must be finite and
within −180 to 180. Create and edit trim titles, descriptions, and addresses.
A nonblank description must contain at least 5 characters. Blank descriptions
and addresses are stored as null. On edit, omitting those fields preserves their
saved values.

Photo edit rule: `retained_media_ids` is a **JSON string array** of existing
media ids to keep, e.g. `retained_media_ids: "[\"id1\",\"id2\"]"`. Omitted =
legacy behavior (new files replace all; no files touches nothing). Explicit
(including `[]`) = keep exactly those. Retained + new must total 1–3, else
400. Unknown ids → 400.

## Location (`/api/location`)

| Method | Path | Auth | Body | Response `data` |
|---|---|---|---|---|
| GET | `/api/location/locations?district_id=` | no | — | `[{id: string, name}]` from live local-level data (721+ rows); `id` is `String(local_levels.id)` |
| GET | `/api/location/report-areas?latitude=&longitude=` | no | — | `[{id: string, name}]` for municipalities covering the pin. An empty list means the pin has no supported municipality. |
| PATCH | `/api/location/location` | Bearer | `{location_id}` — must be an id from the list above | `UserData` |

## Nepal geo (`/api/nepal`, all GETs public)

`GET /provinces` → `[{id, name}]`; `GET /provinces/{id}/districts` →
`[{id, name}]`; `GET /districts/{id}/local[?local_level_type=]`
→ `[{id, name, type}]`. `POST /seed` is admin-only.

## KYC (`/api/kyc`, Bearer required)

KYC is optional for citizen actions. Reporting, tracking, editing/deleting an
eligible own report, upvoting, notifications and account changes require no KYC
approval. Authentication, ownership and report-status rules still apply. Mobile
must keep these actions available for citizens who have never submitted KYC and
for pending, rejected and approved citizens.

Mobile shows pending submissions as in review with a decision notification next,
and approved submissions as verified with no further action. Rejected submissions
show `reviewer_note` and reopen the saved details for correction. Successful
resubmission resets status to pending and clears the old reviewer note.

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/kyc/submit` | multipart: `fullName`, `citizenshipNumber`, `gender` (`male`, `female`, `other`), `dateOfBirth`, `issuedDate` (both `YYYY-MM-DD`), `wardNumber` (positive whole number), `tole` (optional), `province`, `district`, `municipality` (JSON objects with integer `id` and `name` from the Nepal API), files `selfiePhoto`, `documentFrontPhoto`, `documentBackPhoto` (images, ≤5 MB; all required initially; omitted files on rejected resubmissions retain the citizen’s own saved documents) | 201 with pending status. Resubmission returns 409 while pending or approved and is allowed after rejection. |
| GET | `/api/kyc/me` | — | own submission + status + `reviewer_note`; `province`, `district`, `municipality` are `{id: integer, name}` picker values resolved from the saved local level (null for unavailable legacy areas, which must be selected again); `documents: {selfie, front, back}` link paths, never file paths |
| GET | `/api/kyc/documents/{selfie\|front\|back}[?user_id=]` | — | Private image bytes from the database, with the verified media type and `Cache-Control: private, no-store`. Citizens can read their own documents. Admins can read a submission for the specified user. |

Identity documents are stored privately in the database and never exposed as
public URLs. Photo replacements and corrected details commit together. Omitted
photos are retained; obsolete legacy disk files are deleted after commit.

The issue date must be on or after the date of birth, and both dates must be
on or before today's date in Nepal. The API checks that the area IDs and names
match the same municipality, district, and province. Invalid values use field
errors with `detail[].loc` set to `["body", "<form field>"]`. KYC responses
return `date_of_birth` and `issued_date` as `YYYY-MM-DD`.

## Notifications (`/api/notifications`, Bearer required)

| Method | Path | Response |
|---|---|---|
| GET | `/api/notifications?page&limit` | `{notifications: [{id, type, title, message, read, created_at, issue_id?, destination}], meta: {total, page, limit, total_pages}, unread_count}` |
| PATCH | `/api/notifications/{id}/read` | Notification with `read: true` and the same `destination` (owner only, else 404; repeated reads are safe) |
| DELETE | `/api/notifications` | `{message}` (clears own list) |

Generated server-side: welcome on register, upvote on someone else's vote,
status changes, KYC decisions.

`destination` is `{type: "report", issue_id}` for report notifications,
`{type: "kyc"}` for verification updates, and `null` for informational messages.
It is derived from existing notification metadata, including older records;
no migration is needed. Destinations identify in-app resources, never arbitrary
URLs. KYC opens the signed-in citizen's current verification status.
`unread_count` counts all unread messages for the signed-in citizen, across
every page. Clients reuse this count for Home and refetch it after reads,
clearing the inbox, and returning to the foreground.

## Files (`/api/files`, public)

`GET /api/files/{issues|profiles}/{name}` serves active public photos from
local storage or Cloudinary with `Cache-Control: no-store`. Retired URLs
return 404. Older direct Cloudinary URLs are revoked through CDN invalidation.
`kyc` is never servable here.

## Admin (`/api/admin`, admin or superadmin required)

Issue references use the full UUID in `id`, including in URLs and displayed
references. Admin issue lists, details and subscriber issue history return
`upvote_count: null` until vote counts are loaded by those queries. Clients hide
null or missing counts; an actual integer zero remains a valid count. Aggregate
subscriber upvotes are deferred and are not part of the subscriber API.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/admin/issues?page&limit&status&category_id&search&sort&south&north&west&east` | — | paginated results with reporter details and optional filters; bounds are inclusive and applied before pagination/counts. Supply all four finite bounds together, ordered south ≤ north and west ≤ east, within latitude ±90 and longitude ±180; invalid bounds return 422. Omit bounds for the full directory. |
| GET | `/api/admin/issues/overview` | — | `{open, in_progress, resolved, closed, total_issues, total_users, kyc_pending}` |
| PATCH | `/api/admin/issues/{id}/status` | `{status}` | Applies the moderation transition policy (409 for an invalid transition), records the change and notifies the owner |
| GET | `/api/admin/kyc?page&limit&status&search&sort&submitted_on` | — | submissions with status; literal case-insensitive search by applicant name or citizenship number (max 200 characters), applied before counts and pagination; optional `submitted_on` (YYYY-MM-DD, Nepal time); sort by `newest` (default), `oldest`, `name_asc`, or `name_desc` |
| GET | `/api/admin/kyc/{id}` | — | standalone submission lookup, 404 if missing |
| PATCH | `/api/admin/kyc/{id}` | `{status: approved\|rejected, note?}` | notifies the user; rejection requires a nonblank reason, approval note is optional |

Admin KYC list, detail and review responses include `user_id` alongside the
submission fields. Load each document through authenticated
`GET /api/kyc/documents/{selfie|front|back}?user_id={user_id}`. Portal cookies
are accepted; private documents and admin KYC responses use `private, no-store`.
Citizen KYC responses keep their existing fields.

## Status codes

422 validation, 400 bad input/state, 401 missing or invalid credentials, 403
forbidden (incl. insufficient role or non-owner), 404 missing, 409 conflict
(duplicate register/category, KYC resubmit guard, seeded data), 500/503
server/unconfigured uploads.
