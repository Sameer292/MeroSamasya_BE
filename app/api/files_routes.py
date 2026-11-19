from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.storage import PUBLIC_KINDS, local_path

router = APIRouter()


@router.get("/{kind}/{name}")
async def serve_file(kind: str, name: str):
    # Public uploads only (issue photos, profile pictures). KYC docs are
    # served through the authorized /api/kyc/documents endpoint instead.
    if kind not in PUBLIC_KINDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    try:
        path = local_path(kind, name)
    except (ValueError, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    return FileResponse(path)
