import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv
import asyncio

load_dotenv(".env")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

async def upload_image(file_bytes: bytes, citizen_id: str, issue_id: str) -> str:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: cloudinary.uploader.upload(
            file_bytes,
            folder=f"merosamasya/{citizen_id}/{issue_id}",
            resource_type="image",
        )
    )
    return result["secure_url"]