import os
from datetime import datetime, timedelta
from uuid import uuid4

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status

load_dotenv(".env")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_LIFETIME = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")))
REFRESH_LIFETIME = timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "15")))


def create_token(
    user_id: str, session_id: str, *, refresh: bool = False, now: datetime
) -> str:
    lifetime = REFRESH_LIFETIME if refresh else ACCESS_LIFETIME
    claims = {
        "sub": user_id,
        "sid": session_id,
        "refresh": refresh,
        "exp": now + lifetime,
        "jti": str(uuid4()),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_token_session(
    token: str, *, refresh: bool = False, allow_expired: bool = False
) -> tuple[str, str | None]:
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={
                "require": ["sub", "exp", "refresh"],
                "verify_exp": not allow_expired,
            },
        )
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired") from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from error

    subject = claims["sub"]
    session_id = claims.get("sid")
    if claims["refresh"] is not refresh or not isinstance(subject, str) or not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    if "sid" in claims and (
        not isinstance(session_id, str) or not 0 < len(session_id) <= 64
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return subject, session_id
