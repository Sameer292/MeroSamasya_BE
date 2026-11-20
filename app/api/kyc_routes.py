from typing import Optional

from fastapi import APIRouter, Depends, Form, File, UploadFile, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.enum import KycGenderEnum
from app.schemas.schema import KycResponse
from app.services.kyc_service import submit_kyc, get_my_kyc, DOC_FIELDS
from app.models.models import KycSubmission
from app.core.database import get_db
from app.core.storage import local_path
from app.core.admin_config import NO_STORE
from app.dependencies.admin_deps import AdminSessionCookie, check_admin_role, require_admin
from app.dependencies.auth_deps import BearerCredentials, get_current_user

router = APIRouter()


@router.post(
    "/submit", response_model=KycResponse, status_code=status.HTTP_201_CREATED
)
async def submit(
    fullName: str = Form(...),
    citizenshipNumber: str = Form(...),
    gender: KycGenderEnum = Form(...),
    dateOfBirth: str = Form(...),
    issuedDate: str = Form(...),
    wardNumber: str = Form(...),
    tole: Optional[str] = Form(None),
    province: str = Form(...),
    district: str = Form(...),
    municipality: str = Form(...),
    selfiePhoto: Optional[UploadFile] = File(None),
    documentFrontPhoto: Optional[UploadFile] = File(None),
    documentBackPhoto: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await submit_kyc(
        str(current_user.id),
        fullName,
        citizenshipNumber,
        gender,
        dateOfBirth,
        issuedDate,
        wardNumber,
        tole,
        province,
        district,
        municipality,
        selfiePhoto,
        documentFrontPhoto,
        documentBackPhoto,
        db,
    )


@router.get("/me", response_model=KycResponse, status_code=status.HTTP_200_OK)
async def my_kyc(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_my_kyc(str(current_user.id), db)


@router.get("/documents/{doc}")
async def get_document(
    doc: str,
    credentials: BearerCredentials,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    session: AdminSessionCookie = None,
):
    field = dict(DOC_FIELDS).get(doc)
    if field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    if credentials is None and session:
        current_user = await require_admin(credentials, db, session)
    else:
        current_user = await get_current_user(credentials, db)
    target_id = user_id or current_user.id
    if target_id != current_user.id:
        check_admin_role(current_user)
    result = await db.execute(
        select(KycSubmission).where(KycSubmission.user_id == target_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    try:
        path = local_path("kyc", getattr(submission, field))
    except (ValueError, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return FileResponse(path, headers=NO_STORE)
