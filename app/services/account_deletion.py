from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.storage import stored_path
from app.models.admin_auth import AdminSession
from app.models.models import (
    Issue,
    KycDocument,
    KycSubmission,
    Notification,
    Upvote,
    User,
    utcnow,
)
from app.models.photo_storage import PhotoObject
from app.models.refresh_token import RefreshToken
from app.schemas.account_deletion import AccountDeletionRequest
from app.schemas.enum import AccountStatusEnum, UserRole
from app.services.account_access import lock_active_account
from app.services.auth_service import hash_password, verify_password
from app.services.kyc_service import DOC_FIELDS
from app.services.photo_storage import change_photos, photo_url


async def delete_account(db: AsyncSession, user: User, request: AccountDeletionRequest) -> None:
    if user.role != UserRole.citizen:
        raise HTTPException(403, "Only citizen accounts can be deleted here")
    user_id, password = user.id, user.password
    if not await run_in_threadpool(verify_password, request.current_password.get_secret_value(), password):
        raise HTTPException(400, "Current password is incorrect")
    unusable_password = await run_in_threadpool(hash_password, str(uuid4()))

    async with change_photos(db) as photos:
        await lock_active_account(db, user_id)
        current = (await db.execute(
            select(User.password, User.profile_picture_url).where(User.id == user_id)
        )).one()
        if current.password != password:
            raise HTTPException(409, "Account changed during deletion. Please retry.")
        submission = await db.scalar(select(KycSubmission).where(KycSubmission.user_id == user_id))
        if submission is not None:
            # Legacy files share the durable photo cleanup queue; KYC is never publicly served.
            for field in DOC_FIELDS.values():
                name = getattr(submission, field)
                if name:
                    stored_path("kyc", name)
                    url = photo_url("kyc", name)
                    photo = await db.get(PhotoObject, url)
                    if photo is None:
                        photo = PhotoObject(url=url, object_key=f"kyc/{name}")
                        db.add(photo)
                    photo.delete_after = utcnow()
                    photos.retired[url] = False
            await db.execute(delete(KycDocument).where(KycDocument.submission_id == submission.id))
            await db.delete(submission)
        await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        await db.execute(delete(AdminSession).where(AdminSession.user_id == user_id))
        await db.execute(delete(Notification).where(Notification.user_id == user_id))
        await db.execute(delete(Upvote).where(Upvote.user_id == user_id))
        await db.execute(update(Issue).where(Issue.citizen_id == user_id)
                         .values(citizen_id=None, submission_id=None))
        await db.execute(update(User).where(User.id == user_id).values(
            email=f"deleted-{user_id}@deleted.invalid", name=None, phone=None,
            password=unusable_password, location_id=None, profile_picture_url=None,
            account_status=AccountStatusEnum.deleted, deleted_at=utcnow(),
        ))
        if current.profile_picture_url:
            await photos.retire(current.profile_picture_url)
