from datetime import datetime
from app.core.database import db
from app.schemas.schema import UserCreate, UserLogin

async def register_user(user: UserCreate):
    try:
        auth_response = db.auth.sign_up({
            "email": user.email,
            "password": user.password
        })

        if not auth_response.user:
            return {"error": "Registration failed"}

        user_id = auth_response.user.id

        db_response = db.table("Users").insert({
            "id": user_id,
            "email": user.email,
            "first_name": user.first_name,
            "middle_name": user.middle_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role.value,
            "profile_picture_url": user.profile_picture_url,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "deleted_at": None,
            "account_status": "active"
        }).execute()

        if db_response.data is None:
            db.auth.admin.delete_user(user_id)
            return {"error": "Failed to create user profile"}

        return {"message": "User registered successfully", "user_id": user_id}

    except Exception as e:
        return {"error": "Registration failed. Please try again."}


async def login_user(user: UserLogin):
    try:
        auth_response = db.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })

        if not auth_response.user:
            return {"error": "Invalid email or password"}

        db_user = db.table("Users").select("account_status").eq("id", auth_response.user.id).single().execute()
        if not db_user.data or db_user.data["account_status"] != "active":
            return {"error": "Account not active"}

        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "user_id": auth_response.user.id
        }

    except Exception as e:
        return {"error": "Login failed. Please try again."}


async def refresh_access_token(token: str):
    try:
        response = db.auth.refresh_session(token)

        if not response.session:
            return {"error": "Invalid refresh token"}

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "user_id": response.user.id
        }

    except Exception as e:
        return {"error": "Failed to refresh token"}


async def get_user_from_token(token: str):
    try:
        response = db.auth.get_user(token)
        if not response.user:
            return None
        return response.user
    except Exception as e:
        return None