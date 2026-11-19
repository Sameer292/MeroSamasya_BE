import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cloudinary, storage
from app.core.database import AsyncSessionLocal
from app.models.models import Issue, IssueMedia, User, utcnow
from app.models.photo_storage import PhotoObject

logger = logging.getLogger(__name__)
UPLOAD_LEASE = timedelta(minutes=15)
RETRY_DELAY = timedelta(seconds=30)
cleanup_wakeup: asyncio.Event | None = None
LOCAL_URL = re.compile(
    r"/api/files/(issues|profiles)/([a-f0-9]{32}\.(?:jpg|png|webp|bin))"
)
LEGACY_CLOUD_URL = re.compile(
    r"https://res\.cloudinary\.com/([\w-]+)/image/upload/(?:v\d+/)?"
    r"(merosamasya/[\w-]+/[\w-]+/[\w-]+)\.[a-z0-9]+",
    re.ASCII,
)


def photo_url(kind: str, name: str) -> str:
    return f"/api/files/{kind}/{name}"


async def is_photo_referenced(db: AsyncSession, url: str) -> bool:
    report_photo = exists().where(
        IssueMedia.url == url,
        IssueMedia.issue_id == Issue.id,
        Issue.deleted_at.is_(None),
    )
    avatar = exists().where(User.profile_picture_url == url)
    return bool(await db.scalar(select(or_(report_photo, avatar))))


class PhotoChanges:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.pending: dict[str, bool] = {}
        self.uploaded: dict[str, str | None] = {}
        self.retired: dict[str, bool] = {}

    async def upload(
        self, file_bytes: bytes, kind: str, content_type: str | None
    ) -> str:
        name = storage.local_name(content_type)
        url = photo_url(kind, name)
        cloud = cloudinary.configured_cloud()
        key = f"merosamasya/photos/{Path(name).stem}" if cloud else f"{kind}/{name}"
        self.pending[url] = bool(cloud)
        async with AsyncSessionLocal.begin() as db:
            db.add(
                PhotoObject(
                    url=url,
                    object_key=key,
                    cloud=cloud,
                    delete_after=utcnow() + UPLOAD_LEASE,
                )
            )
        if cloud:
            image_format = await cloudinary.upload_photo(file_bytes, key)
        else:
            storage.write_local(file_bytes, kind, name)
            image_format = None
        self.pending[url] = False
        self.uploaded[url] = image_format
        return url

    async def retire(self, url: str):
        photo = await self.db.get(PhotoObject, url)
        if photo is None:
            local = LOCAL_URL.fullmatch(url)
            hosted = LEGACY_CLOUD_URL.fullmatch(url)
            if not (local or hosted) or await is_photo_referenced(self.db, url):
                return
            if local:
                photo = PhotoObject(url=url, object_key="/".join(local.groups()))
            else:
                cloud, key = hosted.groups()
                photo = PhotoObject(url=url, object_key=key, cloud=cloud)
            self.db.add(photo)
        photo.delete_after = utcnow()
        self.retired[url] = bool(photo.cloud)

    async def attach_uploads(self):
        for url, image_format in self.uploaded.items():
            result = await self.db.execute(
                update(PhotoObject)
                .where(PhotoObject.url == url, PhotoObject.delete_after > utcnow())
                .values(delete_after=None, image_format=image_format)
            )
            if not result.rowcount:
                raise RuntimeError("The photo upload reservation expired.")


@asynccontextmanager
async def change_photos(db: AsyncSession):
    photos = PhotoChanges(db)
    try:
        yield photos
        await photos.attach_uploads()
        await db.commit()
    except BaseException:
        await db.rollback()
        for url, upload_uncertain in photos.pending.items():
            await clean_photo(url, abandoned=True, recheck=upload_uncertain)
        raise
    else:
        if cleanup_wakeup is not None and any(photos.retired.values()):
            cleanup_wakeup.set()
        for url, hosted in photos.retired.items():
            if not hosted:
                await clean_photo(url)


async def clean_photo(url: str, *, abandoned: bool = False, recheck: bool = False):
    try:
        async with AsyncSessionLocal.begin() as db:
            # Claim with a write so a second worker or a late attachment cannot race deletion.
            claim = update(PhotoObject).where(PhotoObject.url == url)
            due = (
                PhotoObject.delete_after.is_not(None)
                if abandoned
                else PhotoObject.delete_after <= utcnow()
            )
            photo = await db.scalar(
                claim.where(due)
                .values(delete_after=PhotoObject.delete_after)
                .returning(PhotoObject)
            )
            if photo is None:
                return
            try:
                if photo.cloud:
                    delivery = (
                        "upload"
                        if url.startswith("https://")
                        else cloudinary.AUTHENTICATED
                    )
                    await cloudinary.destroy_photo(
                        photo.object_key, photo.cloud, delivery
                    )
                else:
                    kind, name = photo.object_key.split("/")
                    storage.stored_path(kind, name).unlink(missing_ok=True)
            except Exception:
                logger.exception("Photo cleanup failed for %s", url)
                if not recheck:
                    photo.delete_after = utcnow() + RETRY_DELAY
            else:
                # A timed-out hosted upload can still finish after the first delete attempt.
                if not recheck:
                    await db.delete(photo)
    except Exception:
        logger.exception("Could not process photo cleanup for %s", url)


async def retire_deleted_report_photos(db: AsyncSession):
    deleted_media = (
        select(IssueMedia.id).join(Issue).where(Issue.deleted_at.is_not(None))
    )
    photos = PhotoChanges(db)
    urls = await db.scalars(
        delete(IssueMedia)
        .where(IssueMedia.id.in_(deleted_media))
        .returning(IssueMedia.url)
    )
    for url in set(urls):
        await photos.retire(url)
    await db.commit()


async def retry_photo_cleanup():
    global cleanup_wakeup
    wakeup = cleanup_wakeup = asyncio.Event()
    try:
        while True:
            wakeup.clear()
            try:
                async with AsyncSessionLocal() as db:
                    urls = (
                        await db.scalars(
                            select(PhotoObject.url)
                            .where(PhotoObject.delete_after <= utcnow())
                            .order_by(PhotoObject.delete_after)
                            .limit(100)
                        )
                    ).all()
                for url in urls:
                    await clean_photo(url)
            except Exception:
                logger.exception("Could not load pending photo cleanup")
            try:
                await asyncio.wait_for(wakeup.wait(), RETRY_DELAY.total_seconds())
            except TimeoutError:
                pass
    finally:
        cleanup_wakeup = None
