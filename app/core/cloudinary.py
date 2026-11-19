import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv
import asyncio
from fastapi import HTTPException, status

load_dotenv(".env")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


def is_configured() -> bool:
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


async def _upload(file_bytes: bytes, folder: str) -> str:
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image upload is not configured on this server.",
        )
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: cloudinary.uploader.upload(
            file_bytes,
            folder=folder,
            resource_type="image",
        ),
    )
    return result["secure_url"]


async def upload_image(file_bytes: bytes, citizen_id: str, issue_id: str) -> str:
    return await _upload(file_bytes, f"merosamasya/{citizen_id}/{issue_id}")


async def upload_profile_picture(file_bytes: bytes, user_id: str) -> str:
    return await _upload(file_bytes, f"merosamasya/{user_id}/profile_picture")