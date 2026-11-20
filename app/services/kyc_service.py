import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import delete_local, save_local
from app.models.models import KycSubmission
from app.models.nepal_location_models import District, LocalLevel, Province
from app.schemas.enum import KycGenderEnum, KycStatusEnum
from app.services.issue_service import ALLOWED_TYPES, MAX_FILE_BYTES, check_file_bytes

NEPAL_TIMEZONE = ZoneInfo("Asia/Kathmandu")
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


def field_error(field: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}],
    )


def parse_area(raw: str, field: str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        raise field_error(field, f"Select a valid {field}.") from None
    if not isinstance(data, dict):
        raise field_error(field, f"Select a valid {field}.")
    area_id = data.get("id")
    name = data.get("name")
    if (
        type(area_id) is not int
        or not 0 < area_id <= 2_147_483_647
        or not isinstance(name, str)
        or not name.strip()
    ):
        raise field_error(field, f"Select a valid {field}.")
    return data


async def validate_area_chain(
    db: AsyncSession,
    province_data: dict,
    district_data: dict,
    municipality_data: dict,
) -> str:
    result = await db.execute(
        select(LocalLevel, District, Province)
        .join(District, LocalLevel.district_id == District.id)
        .join(Province, District.province_id == Province.id)
        .where(LocalLevel.id == municipality_data["id"])
    )
    row = result.one_or_none()
    if row is None:
        raise field_error("municipality", "Select a valid municipality.")
    level, district, province = row
    if level.name != municipality_data["name"]:
        raise field_error("municipality", "Municipality name does not match the selected ID.")
    if province.id != province_data["id"] or province.name != province_data["name"]:
        raise field_error("province", "Select the province for this municipality.")
    if district.id != district_data["id"] or district.name != district_data["name"]:
        raise field_error("district", "Select the district for this municipality.")
    return str(level.id)


def parse_calendar_date(raw: str, field: str) -> date:
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        raise field_error(field, "Enter a valid date in YYYY-MM-DD format.") from None
    if value.isoformat() != raw:
        raise field_error(field, "Enter a valid date in YYYY-MM-DD format.")
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
    gender: KycGenderEnum,
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
    full_name = full_name.strip()
    citizenship_number = citizenship_number.strip()
    if len(full_name) < 2:
        raise field_error("fullName", "Full name must be at least 2 characters.")
    if len(citizenship_number) < 3:
        raise field_error("citizenshipNumber", "Citizenship number must be at least 3 characters.")
    dob = parse_calendar_date(date_of_birth, "dateOfBirth")
    issued = parse_calendar_date(issued_date, "issuedDate")
    today = datetime.now(NEPAL_TIMEZONE).date()
    if dob > today:
        raise field_error("dateOfBirth", "Date of birth cannot be in the future.")
    if issued > today:
        raise field_error("issuedDate", "Issued date cannot be in the future.")
    if issued < dob:
        raise field_error("issuedDate", "Issued date cannot be before date of birth.")
    ward_number = ward_number.strip()
    if not (ward_number.isascii() and ward_number.isdecimal() and ward_number.lstrip("0")):
        raise field_error("wardNumber", "Enter a positive whole ward number.")

    province_data = parse_area(province, "province")
    district_data = parse_area(district, "district")
    municipality_data = parse_area(municipality, "municipality")
    local_level_id = await validate_area_chain(
        db, province_data, district_data, municipality_data
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
            existing.full_name = full_name
            existing.citizenship_number = citizenship_number
            existing.gender = gender.value
            existing.date_of_birth = dob
            existing.issued_date = issued
            existing.ward_number = ward_number
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
                full_name=full_name,
                citizenship_number=citizenship_number,
                gender=gender.value,
                date_of_birth=dob,
                issued_date=issued,
                ward_number=ward_number,
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
