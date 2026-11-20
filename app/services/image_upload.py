from io import BytesIO
from typing import BinaryIO

from anyio import CapacityLimiter, to_thread
from fastapi import HTTPException, UploadFile
from PIL import Image

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_EDGE = 8192
MAX_IMAGE_PIXELS = 24_000_000
IMAGE_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
decode_slots = CapacityLimiter(4)


class InvalidImage(ValueError):
    pass


def image_content_type(data: bytes) -> str:
    if not data:
        raise InvalidImage("The image file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise InvalidImage("Image is too large. The maximum is 5 MB per image.")
    dimensions_error = "Image dimensions exceed 8192 pixels per side or 24 megapixels."
    try:
        with Image.open(BytesIO(data), formats=list(IMAGE_TYPES)) as image:
            width, height = image.size
            if not (0 < width <= MAX_IMAGE_EDGE and 0 < height <= MAX_IMAGE_EDGE
                    and width * height <= MAX_IMAGE_PIXELS):
                raise InvalidImage(dimensions_error)
            if getattr(image, "is_animated", False):
                raise InvalidImage("Choose a still image.")
            content_type = IMAGE_TYPES[image.format]
            image.verify()
        with Image.open(BytesIO(data), formats=list(IMAGE_TYPES)) as image:
            image.load()
    except InvalidImage:
        raise
    except Image.DecompressionBombError as exc:
        raise InvalidImage(dimensions_error) from exc
    except (OSError, ValueError, SyntaxError, EOFError, OverflowError) as exc:
        raise InvalidImage("Choose a readable JPEG, PNG, or WebP image.") from exc
    return content_type


def read_image_file(file: BinaryIO) -> tuple[bytes, str]:
    data = file.read(MAX_FILE_BYTES + 1)
    return data, image_content_type(data)


async def read_image_upload(upload: UploadFile | None, *field: str | int) -> tuple[bytes, str]:
    try:
        if upload is None:
            raise InvalidImage("Select an image.")
        return await to_thread.run_sync(read_image_file, upload.file, limiter=decode_slots)
    except InvalidImage as exc:
        raise HTTPException(
            status_code=400,
            detail=[{"loc": ["body", *field], "msg": str(exc), "type": "value_error"}],
        ) from None
