"""Replace the app's database contents with the Hetauda showcase dataset."""

import argparse
import asyncio
import os


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--reset-demo-database", action="store_true")
    mode.add_argument("--backfill-demo-media", action="store_true")
    mode.add_argument("--backfill-demo-details", action="store_true")
    args = parser.parse_args()
    target = os.environ.get("SEED_DATABASE_URL")
    if args.backfill_demo_media or args.backfill_demo_details:
        if target:
            os.environ["DATABASE_URL"] = target
        if args.backfill_demo_details:
            from seeder.backfill_details import backfill_demo_details

            print(asyncio.run(backfill_demo_details()))
        else:
            from seeder.backfill import backfill_demo

            print(asyncio.run(backfill_demo()))
        return
    if not os.environ.get("SEED_DEMO_PASSWORD"):
        parser.error("Set SEED_DEMO_PASSWORD before resetting the demo database.")
    if not target:
        parser.error("Set SEED_DATABASE_URL to the demo database and pass --reset-demo-database.")

    os.environ["DATABASE_URL"] = target
    from seeder.reset import reset_and_seed

    summary = asyncio.run(reset_and_seed())
    print(summary)


if __name__ == "__main__":
    main()
