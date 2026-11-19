import os

from dotenv import load_dotenv

load_dotenv(".env")

ADMIN_WEB_ORIGIN = os.getenv("ADMIN_WEB_ORIGIN", "http://localhost:3000").rstrip("/")
ADMIN_COOKIE_SECURE = os.getenv("ADMIN_COOKIE_SECURE", "true").lower() == "true"
ADMIN_COOKIE_NAME = "__Host-admin-session" if ADMIN_COOKIE_SECURE else "admin-session"
NO_STORE = {"Cache-Control": "private, no-store"}
