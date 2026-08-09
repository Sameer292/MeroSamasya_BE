import cloudinary
import cloudinary.uploader
import os
from datetime import date, datetime, timezone
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from app.models.kyc import KYCSubmission
from app.schemas.enum import KYCStatusEnum
from app.schemas.kyc_schema import KYCReviewRequest

load_dotenv(".env")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


def utcnow():
    return datetime.now(timezone.utc)


async def _upload_image(file: UploadFile, folder: str, public_id: str) -> str:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{file.filename}' must be JPEG, PNG, or WebP.",
        )
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{file.filename}' exceeds the 5 MB size limit.",
        )
    try:
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            public_id=public_id,
            resource_type="image",
            overwrite=True,
        )
        return result["secure_url"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image upload failed: {str(e)}",
        )


async def submit_kyc(
    user_id: str,
    full_name: str,
    date_of_birth: date,
    citizenship_number: str,
    citizenship_front: UploadFile,
    citizenship_back: UploadFile,
    selfie: UploadFile,
    db: AsyncSession,
):
    existing_result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        if existing.status == KYCStatusEnum.approved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Your KYC is already approved.",
            )
        if existing.status == KYCStatusEnum.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Your KYC submission is already under review.",
            )
        await db.delete(existing)
        await db.flush()

    dup_result = await db.execute(
        select(KYCSubmission).where(
            KYCSubmission.citizenship_number == citizenship_number
        )
    )
    if dup_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This citizenship number is already registered.",
        )

    folder = f"merosamasya/kyc/{user_id}"
    front_url  = await _upload_image(citizenship_front, folder, "citizenship_front")
    back_url   = await _upload_image(citizenship_back,  folder, "citizenship_back")
    selfie_url = await _upload_image(selfie,            folder, "selfie")

    try:
        kyc = KYCSubmission(
            user_id=user_id,
            full_name=full_name,
            date_of_birth=date_of_birth,
            citizenship_number=citizenship_number,
            citizenship_front_url=front_url,
            citizenship_back_url=back_url,
            selfie_url=selfie_url,
            status=KYCStatusEnum.pending,
        )
        db.add(kyc)
        await db.commit()
        await db.refresh(kyc)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save KYC submission. Please try again.",
        )

    return {
        "message": "KYC submitted successfully. It is now under review.",
        "data": {"kyc_id": kyc.id, "status": kyc.status},
    }


async def get_my_kyc(user_id: str, db: AsyncSession):
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No KYC submission found for your account.",
        )
    return kyc


async def list_kyc_submissions(
    db: AsyncSession,
    filter_status: KYCStatusEnum | None = None,
):
    query = select(KYCSubmission)
    if filter_status:
        query = query.where(KYCSubmission.status == filter_status)
    query = query.order_by(KYCSubmission.submitted_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def review_kyc(
    kyc_id: str,
    admin_id: str,
    review: KYCReviewRequest,
    db: AsyncSession,
):
    if review.action == KYCStatusEnum.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'approved' or 'rejected'.",
        )
    if review.action == KYCStatusEnum.rejected and not review.rejection_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rejection_reason is required when rejecting a KYC.",
        )

    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.id == kyc_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC submission not found.",
        )
    if kyc.status != KYCStatusEnum.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"KYC is already '{kyc.status}'. Only pending submissions can be reviewed.",
        )

    kyc.status           = review.action
    kyc.rejection_reason = review.rejection_reason
    kyc.reviewed_by      = admin_id
    kyc.reviewed_at      = utcnow()

    try:
        await db.commit()
        await db.refresh(kyc)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update KYC status.",
        )

    return {
        "message": f"KYC {review.action} successfully.",
        "data": {"kyc_id": kyc.id, "status": kyc.status},
    }