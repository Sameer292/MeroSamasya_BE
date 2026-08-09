import os
from fastapi import Depends, HTTPException, status
from app.dependencies.auth_deps import get_current_user
from app.models.models import User


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    admin_emails_raw = os.getenv("ADMIN_EMAILS", "")
    admin_emails = [e.strip() for e in admin_emails_raw.split(",") if e.strip()]

    if not admin_emails:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_EMAILS is not configured on the server.",
        )
    if current_user.email not in admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user