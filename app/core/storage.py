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


def save_local(file_bytes: bytes, kind: str, content_type: str | None) -> str:
    """Save bytes under STORAGE_DIR/<kind>/, return the stored file name."""
    ext = EXT_BY_CONTENT_TYPE.get((content_type or "").lower(), ".bin")
    name = f"{uuid.uuid4().hex}{ext}"
    folder = STORAGE_DIR / kind
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(file_bytes)
    return name


def local_path(kind: str, name: str) -> Path:
    """Resolve a stored file, guarding against path traversal."""
    if kind not in PUBLIC_KINDS and kind != "kyc":
        raise ValueError("Unknown file kind")
    clean = Path(name).name
    if not clean or clean != name:
        raise ValueError("Invalid file name")
    path = STORAGE_DIR / kind / clean
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
