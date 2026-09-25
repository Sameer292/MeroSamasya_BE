import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, UploadFile
from app.models.models import KycSubmission
from app.schemas.enum import KycStatusEnum
from app.core.storage import save_local, delete_local
from app.services.issue_service import ALLOWED_TYPES, MAX_FILE_BYTES, check_file_bytes

ALLOWED_GENDERS = {"male", "female", "other"}
DOC_FIELDS = (
    ("selfie", "selfie_path"),
    ("front", "doc_front_path"),
    ("back", "doc_back_path"),
)


def document_links() -> dict:
    return {
        "selfie": "/api/kyc/documents/selfie",
        "front": "/api/kyc/documents/front",
        "back": "/api/kyc/documents/back",
    }


def serialize_kyc(sub: KycSubmission) -> dict:
    return {
        "id": str(sub.id),
        "full_name": sub.full_name,
        "citizenship_number": sub.citizenship_number,
        "gender": sub.gender,
        "date_of_birth": sub.date_of_birth,
        "issued_date": sub.issued_date,
        "ward_number": sub.ward_number,
        "tole": sub.tole,
        "province_name": sub.province_name,
        "district_name": sub.district_name,
        "municipality_name": sub.municipality_name,
        "local_level_id": sub.local_level_id,
        "status": sub.status.value if isinstance(sub.status, KycStatusEnum) else sub.status,
        "reviewer_note": sub.reviewer_note,
        "documents": document_links(),
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
    }


def parse_area(raw: str | None, field: str) -> dict:
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing field: {field}",
        )
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field} payload.",
        )
    if not isinstance(data, dict) or not data.get("name"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field} payload: object with name required.",
        )
    return data


async def validate_area_chain(
    db: AsyncSession,
    province_name: str,
    district_name: str,
    municipality_data: dict,
) -> str | None:
    """Bind the claimed area to live Nepal data.

    When the client sends a municipality id (it always does: objects come
    from this API), the id must exist and its district/province names must
    match the claimed ones, so callers cannot invent arbitrary areas.
    Returns the verified local_level id, or None when no id was sent.
    """
    from app.models.nepal_location_models import District, LocalLevel, Province

    muni_id = municipality_data.get("id")
    if muni_id is None:
        return None
    try:
        level_id = int(muni_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid municipality id.",
        )
    result = await db.execute(
        select(LocalLevel, District, Province)
        .join(District, LocalLevel.district_id == District.id)
        .join(Province, District.province_id == Province.id)
        .where(LocalLevel.id == level_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Municipality not found.",
        )
    level, district, province = row
    if (
        district.name != district_name
        or province.name != province_name
        or level.name != municipality_data["name"]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Area mismatch: municipality does not belong to the claimed district/province.",
        )
    return str(level.id)


def parse_date(raw: str | None, field: str) -> datetime:
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing field: {field}",
        )
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field}: must be ISO date.",
        )
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


async def read_doc_file(upload: UploadFile | None, field: str) -> bytes:
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing file: {field}",
        )
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type for {field}: {upload.content_type}.",
        )
    # ponytail: bounded read, a huge upload never fully lands in memory
    file_bytes = await upload.read(MAX_FILE_BYTES + 1)
    check_file_bytes(file_bytes)
    return file_bytes


async def submit_kyc(
    user_id: str,
    full_name: str,
    citizenship_number: str,
    gender: str,
    date_of_birth: str,
    issued_date: str,
    ward_number: str,
    tole: str | None,
    province: str,
    district: str,
    municipality: str,
    selfie: UploadFile | None,
    doc_front: UploadFile | None,
    doc_back: UploadFile | None,
    db: AsyncSession,
):
    if not full_name or len(full_name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid full name."
        )
    if not citizenship_number or len(citizenship_number.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid citizenship number.",
        )
    gender = (gender or "").strip().lower()
    if gender not in ALLOWED_GENDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid gender."
        )
    dob = parse_date(date_of_birth, "dateOfBirth")
    issued = parse_date(issued_date, "issuedDate")
    now = datetime.now(timezone.utc)
    if dob > now or issued > now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dates cannot be in the future.",
        )
    if issued < dob:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issued date cannot be before date of birth.",
        )
    if not ward_number or not str(ward_number).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ward number required."
        )

    province_data = parse_area(province, "province")
    district_data = parse_area(district, "district")
    municipality_data = parse_area(municipality, "municipality")
    local_level_id = await validate_area_chain(
        db, province_data["name"], district_data["name"], municipality_data
    )

    selfie_bytes = await read_doc_file(selfie, "selfiePhoto")
    front_bytes = await read_doc_file(doc_front, "documentFrontPhoto")
    back_bytes = await read_doc_file(doc_back, "documentBackPhoto")

    # ponytail: identity docs stay on local disk, never public URLs
    selfie_name = save_local(selfie_bytes, "kyc", selfie.content_type)
    front_name = save_local(front_bytes, "kyc", doc_front.content_type)
    back_name = save_local(back_bytes, "kyc", doc_back.content_type)
    new_files = (selfie_name, front_name, back_name)

    try:
        result = await db.execute(
            select(KycSubmission).where(KycSubmission.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None and existing.status in (
            KycStatusEnum.pending,
            KycStatusEnum.approved,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "KYC already under review."
                    if existing.status == KycStatusEnum.pending
                    else "KYC already verified."
                ),
            )
        old_files: tuple | None = None
        if existing:
            old_files = (
                existing.selfie_path,
                existing.doc_front_path,
                existing.doc_back_path,
            )
            existing.full_name = full_name.strip()
            existing.citizenship_number = citizenship_number.strip()
            existing.gender = gender
            existing.date_of_birth = dob
            existing.issued_date = issued
            existing.ward_number = str(ward_number).strip()
            existing.tole = tole or None
            existing.province_name = province_data["name"]
            existing.district_name = district_data["name"]
            existing.municipality_name = municipality_data["name"]
            existing.local_level_id = local_level_id
            existing.selfie_path = selfie_name
            existing.doc_front_path = front_name
            existing.doc_back_path = back_name
            existing.status = KycStatusEnum.pending
            existing.reviewer_note = None
            submission = existing
            message = "KYC resubmitted successfully"
        else:
            submission = KycSubmission(
                user_id=user_id,
                full_name=full_name.strip(),
                citizenship_number=citizenship_number.strip(),
                gender=gender,
                date_of_birth=dob,
                issued_date=issued,
                ward_number=str(ward_number).strip(),
                tole=tole or None,
                province_name=province_data["name"],
                district_name=district_data["name"],
                municipality_name=municipality_data["name"],
                local_level_id=local_level_id,
                selfie_path=selfie_name,
                doc_front_path=front_name,
                doc_back_path=back_name,
                status=KycStatusEnum.pending,
            )
            db.add(submission)
            message = "KYC submitted successfully"
        await db.commit()
        await db.refresh(submission)
    except HTTPException:
        await db.rollback()
        for name in new_files:
            delete_local("kyc", name)
        raise
    except Exception:
        await db.rollback()
        for name in new_files:
            delete_local("kyc", name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit KYC. Please try again.",
        )

    # ponytail: old docs deleted only after the new paths committed
    if old_files:
        for name in old_files:
            delete_local("kyc", name)

    return {"message": message, "data": serialize_kyc(submission)}


async def get_my_kyc(user_id: str, db: AsyncSession):
    result = await db.execute(
        select(KycSubmission).where(KycSubmission.user_id == user_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No KYC submission found.",
        )
    return {"message": "KYC fetched successfully", "data": serialize_kyc(submission)}
