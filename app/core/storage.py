import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env")

# Local disk fallback used when Cloudinary is not configured, and always for
# private KYC identity documents (never served from public URLs).
STORAGE_DIR = Path(os.getenv("LOCAL_STORAGE_DIR", "./storage"))

EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

PUBLIC_KINDS = {"issues", "profiles"}


def local_name(content_type: str | None) -> str:
    ext = EXT_BY_CONTENT_TYPE.get((content_type or "").lower(), ".bin")
    return f"{uuid.uuid4().hex}{ext}"


def write_local(file_bytes: bytes, kind: str, name: str):
    path = stored_path(kind, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_bytes)


def save_local(file_bytes: bytes, kind: str, content_type: str | None) -> str:
    name = local_name(content_type)
    write_local(file_bytes, kind, name)
    return name


def stored_path(kind: str, name: str) -> Path:
    if kind not in PUBLIC_KINDS and kind != "kyc":
        raise ValueError("Unknown file kind")
    if not name or name == ".." or Path(name).name != name:
        raise ValueError("Invalid file name")
    return STORAGE_DIR / kind / name


def local_path(kind: str, name: str) -> Path:
    path = stored_path(kind, name)
    if not path.is_file():
        raise FileNotFoundError(name)
    return path


def delete_local(kind: str, name: str | None):
    """Best-effort removal of a replaced file."""
    if not name:
        return
    try:
        local_path(kind, name).unlink()
    except (ValueError, FileNotFoundError, OSError):
        pass
