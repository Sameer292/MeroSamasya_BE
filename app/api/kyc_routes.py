from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth_deps import get_current_user
from app.dependencies.admin_deps import get_admin_user
from app.models.models import User
from app.schemas.enum import KYCStatusEnum
from app.schemas.kyc_schema import (
    KYCAdminListItem,
    KYCReviewRequest,
    KYCStatusResponse,
    KYCSubmitResponse,
)
from app.services import kyc_service

router = APIRouter()


@router.post(
    "/submit",
    response_model=KYCSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit KYC documents for verification",
)
async def submit_kyc(
    full_name: str = Form(..., description="Legal full name as on citizenship card"),
    date_of_birth: date = Form(..., description="Date of birth (YYYY-MM-DD)"),
    citizenship_number: str = Form(..., description="Citizenship certificate number"),
    citizenship_front: UploadFile = File(..., description="Front photo of citizenship card"),
    citizenship_back: UploadFile = File(..., description="Back photo of citizenship card"),
    selfie: UploadFile = File(..., description="Clear selfie / face photo"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await kyc_service.submit_kyc(
        user_id=str(current_user.id),
        full_name=full_name,
        date_of_birth=date_of_birth,
        citizenship_number=citizenship_number,
        citizenship_front=citizenship_front,
        citizenship_back=citizenship_back,
        selfie=selfie,
        db=db,
    )


@router.get(
    "/me",
    response_model=KYCStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get your own KYC submission and status",
)
async def get_my_kyc(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await kyc_service.get_my_kyc(str(current_user.id), db)


@router.get(
    "/admin/list",
    response_model=List[KYCAdminListItem],
    status_code=status.HTTP_200_OK,
    summary="[Admin] List all KYC submissions",
)
async def list_kyc(
    filter_status: Optional[KYCStatusEnum] = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await kyc_service.list_kyc_submissions(db, filter_status)


@router.patch(
    "/admin/review/{kyc_id}",
    status_code=status.HTTP_200_OK,
    summary="[Admin] Approve or reject a KYC submission",
)
async def review_kyc(
    kyc_id: str,
    review: KYCReviewRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await kyc_service.review_kyc(
        kyc_id=kyc_id,
        admin_id=str(admin.id),
        review=review,
        db=db,
    )