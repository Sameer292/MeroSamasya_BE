import asyncio
from typing import Annotated
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cloudinary
from app.core.database import get_db
from app.core.storage import PUBLIC_KINDS, local_path
from app.models.photo_storage import PhotoObject
from app.services.photo_storage import is_photo_referenced, photo_url

router = APIRouter()


@router.get("/{kind}/{name}")
async def serve_file(
    kind: str, name: str, db: Annotated[AsyncSession, Depends(get_db)]
):
    headers = {"Cache-Control": "no-store"}
    missing = HTTPException(
        status.HTTP_404_NOT_FOUND, "File not found", headers=headers
    )
    if kind not in PUBLIC_KINDS:
        raise missing
    url = photo_url(kind, name)
    photo = await db.get(PhotoObject, url)
    if photo is not None and photo.delete_after is not None:
        raise missing
    if photo is not None and photo.cloud:
        try:
            if photo.cloud != cloudinary.configured_cloud():
                raise ValueError("The upload's Cloudinary environment is unavailable.")
            content, mime_type = await asyncio.to_thread(
                cloudinary.read_photo, photo.object_key, photo.cloud, photo.image_format
            )
        except HTTPError as error:
            if error.code == 404:
                raise missing from error
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "Photo unavailable", headers=headers
            ) from error
        except (URLError, OSError, ValueError) as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "Photo unavailable", headers=headers
            ) from error
        return Response(content, media_type=mime_type, headers=headers)
    try:
        path = local_path(kind, name)
    except (ValueError, FileNotFoundError) as error:
        raise missing from error
    if photo is None and not await is_photo_referenced(db, url):
        raise missing
    return FileResponse(path, headers=headers)
