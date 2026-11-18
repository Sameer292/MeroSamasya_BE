import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status

load_dotenv(".env")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_LIFETIME = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)))
REFRESH_LIFETIME = timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", 15)))


def create_token(
    user_id: str, *, refresh: bool = False, now: datetime | None = None
) -> str:
    lifetime = REFRESH_LIFETIME if refresh else ACCESS_LIFETIME
    claims = {
        "sub": user_id,
        "refresh": refresh,
        "exp": (now or datetime.now(timezone.utc)) + lifetime,
        "jti": str(uuid4()),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_token_subject(token: str, *, refresh: bool = False) -> str:
    try:
        claims = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "refresh"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired") from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from error

    subject = claims["sub"]
    if claims["refresh"] is not refresh or not isinstance(subject, str) or not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return subject
