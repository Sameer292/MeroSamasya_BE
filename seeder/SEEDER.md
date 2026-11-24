# Hetauda showcase database

`seed.py` replaces application data in a **disposable demo database**. It downloads
the public sample images and checks that all report pins are inside Hetauda
before opening a database connection.

## Run only when ready to replace the target database

1. Verify that the target is a dedicated demo database and back up anything you
   need to keep. Start the app once to initialize its schema and location
   catalog, then stop app instances connected to it while resetting.
2. Set `SEED_DATABASE_URL` to that database's SQLAlchemy connection URL. For
   Supabase, use a Postgres connection string with a database role that owns
   the app tables or has the required permissions. Use the
   `postgresql+asyncpg://` scheme. Keep the connection string out of Git.
3. Set `LOCAL_STORAGE_DIR` to the same persistent directory used by the API
   instance serving the demo. Report and profile images are downloaded there.
4. Set `SEED_DEMO_PASSWORD` for the demo accounts and optionally
   `SEED_DEMO_ADMIN_EMAIL` for the admin login. Then run:

   ```bash
   uv run python -m seeder.seed --reset-demo-database
   ```

Supabase is supported through its
[Postgres connection](https://supabase.com/docs/guides/database/connecting-to-postgres).
The seeder clears the application's non-location tables in `public` and inserts
the showcase dataset in a single transaction. It preserves `provinces`,
`districts`, and `local_levels`, including every existing ID.
It also preserves Supabase-managed schemas, unrelated tables, Cloudinary
objects, and existing files on disk. PostgreSQL
uses `RESTRICT` so a foreign key from an unrelated table blocks the reset.
SQLite is supported for local demos. Use the app's current schema on upgraded
databases so any legacy column migrations have already been applied.

The seeder rebuilds the standard categories and references the existing
Hetauda Sub-Metropolitan City record for every seeded account and report.

## Demo data

| Item | Count |
| --- | ---: |
| Citizens | 100 |
| Admins | 1 |
| Approved KYC | 80 |
| Pending KYC | 10 |
| Rejected KYC | 5 |
| Citizens without KYC | 5 |
| Open issues | 60 |
| In-progress issues | 23 |
| Resolved issues | 16 |
| Closed issues | 9 |
| Distinct citizen reporters | 60 |

Report upvote counts range from 0 to 40, with many at or below 30. Each seeded upvote comes from a
distinct approved citizen other than the reporter.
Reports have one to three attachments, within the app's upload limit.

Use `admin@gmail.com` for the admin or `ram@example.com` for a verified citizen.
Every demo account uses `password@123`. Other citizens use simple names such as
`sita.shrestha@example.com`. The reserved example domain keeps those accounts
distinct from real inboxes. The admin has no reports.

KYC previews use illustrated avatars and synthetic JPEG cards labeled
**DEMO ONLY – NOT A VALID ID**. These cards contain no real identity documents
and use the same private document storage as normal KYC submissions.

## Image credits

Issue photos are illustrative samples. They do not depict the seeded report
locations. The seeder resizes the images and strips embedded metadata.

- [Marked Pothole](https://commons.wikimedia.org/wiki/File:Marked_Pothole.jpg) by Prosthetic Head, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- [Hole in the road](https://commons.wikimedia.org/wiki/File:Hole_in_the_road_-_Flickr_-_Robbie1.jpg) by Robbie Sproule, [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/).
- [Worn cracked asphalt pavement](https://commons.wikimedia.org/wiki/File:Worn_cracked_asphalt_pavement.jpg) by John Harvey, public domain.
- [Flooded street in Sacramento](https://commons.wikimedia.org/wiki/File:Flooded_street_in_Sacramento_with_stop_sign_and_whirlpool.jpg) by Roc0ast3r, [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
- [Flooded street in town](https://commons.wikimedia.org/wiki/File:Flooded_street_in_town.jpg) by Annatsach, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- [Flooded street and vehicles](https://commons.wikimedia.org/wiki/File:Flooded_street_and_vehicles.JPG) by MarkBuckawicki, [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
- [Street Garbage](https://commons.wikimedia.org/wiki/File:Street_Garbage.jpg) by Gaurav Dhwaj Khadka, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- [Cracked sidewalk 1](https://commons.wikimedia.org/wiki/File:Cracked_sidewalk_1.jpg) by Downtowngal, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- [Lorelei avatars](https://www.dicebear.com/licenses/) by Lisa Wischofsky via DiceBear, [CC0](https://creativecommons.org/publicdomain/zero/1.0/).


## Fill gaps in an existing demo

Run `uv run python -m seeder.seed --backfill-demo-media` to add a detail image to
single-photo Hetauda demo reports and add missing history to closed demo reports.
The backfill uses the configured database and media directory without resetting
tables. Set `SEED_DATABASE_URL` to select a different demo database.

Run `uv run python -m seeder.seed --backfill-demo-details` to top up existing
demo vote counts and refresh the headings on synthetic KYC images.
