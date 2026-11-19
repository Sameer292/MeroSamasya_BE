import asyncio
import os
from urllib.request import urlopen

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from dotenv import load_dotenv

load_dotenv(".env")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

AUTHENTICATED = "authenticated"
TIMEOUT = 8


def configured_cloud() -> str | None:
    config = cloudinary.config()
    if config.api_key and config.api_secret:
        return config.cloud_name
    return None


async def upload_photo(file_bytes: bytes, public_id: str) -> str:
    result = await asyncio.to_thread(
        cloudinary.uploader.upload,
        file_bytes,
        public_id=public_id,
        resource_type="image",
        type=AUTHENTICATED,
        overwrite=False,
        allowed_formats=["jpg", "jpeg", "png", "webp"],
        timeout=TIMEOUT,
    )
    return result["format"]


async def destroy_photo(public_id: str, cloud: str, delivery_type: str):
    if cloud != configured_cloud():
        raise RuntimeError("The upload's Cloudinary environment is unavailable.")
    result = await asyncio.to_thread(
        cloudinary.uploader.destroy,
        public_id,
        type=delivery_type,
        resource_type="image",
        invalidate=True,
        timeout=TIMEOUT,
    )
    if result.get("result") not in {"ok", "not found"}:
        raise RuntimeError("Cloudinary did not confirm deletion.")


def read_photo(public_id: str, cloud: str, image_format: str) -> tuple[bytes, str]:
    url, _ = cloudinary_url(
        public_id,
        cloud_name=cloud,
        format=image_format,
        secure=True,
        resource_type="image",
        type=AUTHENTICATED,
        sign_url=True,
    )
    with urlopen(url, timeout=TIMEOUT) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Unexpected Cloudinary photo content type.")
        return response.read(), content_type
