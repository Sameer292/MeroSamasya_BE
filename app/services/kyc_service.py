import json
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from anyio import to_thread
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, exists, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import delete_local, local_path
from app.models.models import KycDocument, KycSubmission, User
from app.models.nepal_location_models import District, LocalLevel, Province
from app.schemas.enum import KycGenderEnum, KycStatusEnum
from app.services.image_upload import read_image_file, read_image_upload

NEPAL_TIMEZONE = ZoneInfo("Asia/Kathmandu")
DOC_FIELDS = {"selfie": "selfie_path", "front": "doc_front_path", "back": "doc_back_path"}
logger = logging.getLogger(__name__)


def document_links() -> dict:
    return {kind: f"/api/kyc/documents/{kind}" for kind in DOC_FIELDS}


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


def read_legacy_document(name: str) -> tuple[bytes, str]:
    with local_path("kyc", name).open("rb") as file:
        return read_image_file(file)


async def import_legacy_kyc_documents(db: AsyncSession):
    insert = sqlite_insert if db.get_bind().dialect.name == "sqlite" else postgres_insert
    for kind, field in DOC_FIELDS.items():
        path = getattr(KycSubmission, field)
        documents = await db.execute(
            select(KycSubmission.id, path).where(
                path != "",
                ~exists().where(
                    KycDocument.submission_id == KycSubmission.id, KycDocument.kind == kind
                ),
            ).order_by(KycSubmission.id)
        )
        for submission_id, name in documents:
            try:
                data, content_type = await to_thread.run_sync(read_legacy_document, name)
            except (OSError, ValueError):
                logger.warning("Could not import KYC %s document for submission %s", kind, submission_id)
                continue
            await db.execute(
                insert(KycDocument).values(
                    submission_id=submission_id, kind=kind, content_type=content_type, data=data
                ).on_conflict_do_nothing(index_elements=[KycDocument.submission_id, KycDocument.kind])
            )
        await db.commit()


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

    documents = {
        "selfie": await read_image_upload(selfie, "selfiePhoto"),
        "front": await read_image_upload(doc_front, "documentFrontPhoto"),
        "back": await read_image_upload(doc_back, "documentBackPhoto"),
    }
    values = {
        "full_name": full_name,
        "citizenship_number": citizenship_number,
        "gender": gender.value,
        "date_of_birth": dob,
        "issued_date": issued,
        "ward_number": ward_number,
        "tole": tole or None,
        "province_name": province_data["name"],
        "district_name": district_data["name"],
        "municipality_name": municipality_data["name"],
        "local_level_id": local_level_id,
        "status": KycStatusEnum.pending,
        "reviewer_note": None,
    }

    try:
        # Serialize submissions for the same user, including their first submission.
        if db.get_bind().dialect.name == "sqlite":
            await db.execute(update(User.__table__).where(User.id == user_id)
                             .values(updated_at=User.updated_at))
        else:
            await db.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
        submission = await db.scalar(
            select(KycSubmission).where(KycSubmission.user_id == user_id).with_for_update(key_share=True)
        )
        if submission is not None and submission.status in (
            KycStatusEnum.pending,
            KycStatusEnum.approved,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "KYC already under review."
                    if submission.status == KycStatusEnum.pending
                    else "KYC already verified."
                ),
            )
        old_files = ()
        if submission is not None:
            old_files = tuple(getattr(submission, field) for field in DOC_FIELDS.values())
            for field in DOC_FIELDS.values():
                setattr(submission, field, "")
            for field, value in values.items():
                setattr(submission, field, value)
            await db.execute(
                delete(KycDocument).where(KycDocument.submission_id == submission.id)
            )
            message = "KYC resubmitted successfully"
        else:
            submission = KycSubmission(user_id=user_id, **values)
            db.add(submission)
            message = "KYC submitted successfully"
        await db.flush()
        db.add_all([
            KycDocument(submission_id=submission.id, kind=kind, data=data, content_type=content_type)
            for kind, (data, content_type) in documents.items()
        ])
        await db.refresh(submission)
        response = {"message": message, "data": serialize_kyc(submission)}
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit KYC. Please try again.",
        )

    for name in old_files:
        delete_local("kyc", name)
    return response


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
