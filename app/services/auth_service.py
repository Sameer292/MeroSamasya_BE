from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import supabase_auth
from app.models.models import User
from app.schemas.schema import UserCreate, UserLogin

async def register_user(user: UserCreate, db: AsyncSession):
    user_id = None
    try:
        auth_response = supabase_auth.auth.sign_up({
            "email": user.email,
            "password": user.password
        })

        if not auth_response.user:
            return {"error": "Registration failed"}

        user_id = auth_response.user.id
        print("Auth user created:", user_id)  # check 1

        new_user = User(
            id=user_id,
            email=user.email,
            first_name=user.first_name,
            middle_name=user.middle_name,
            last_name=user.last_name,
            phone=user.phone,
            role="citizen",
            profile_picture_url=None,
            account_status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            deleted_at=None,
        )

        db.add(new_user)
        print("User added to session")
        
        await db.commit()
        print("Commit successful")

        return {"message": "User registered successfully", "user_id": user_id}

    except Exception as e:
        print("ERROR:", str(e))
        await db.rollback()
        if user_id is not None:
            try:
                supabase_auth.auth.admin.delete_user(str(user_id))
                print("Auth user deleted successfully")
            except Exception as delete_error:
                print("Failed to delete auth user:", delete_error)
        return {"error": f"Registration failed: {str(e)}"}


async def login_user(user: UserLogin, db: AsyncSession):
    try:
        auth_response = supabase_auth.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })

        if not auth_response.user:
            return {"error": "Invalid email or password"}

        result = await db.execute(
            select(User).where(User.id == auth_response.user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user or db_user.account_status != "active":
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
        response = supabase_auth.auth.refresh_session(token)

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
        response = supabase_auth.auth.get_user(token)
        if not response.user:
            return None
        return response.user
    except Exception as e:
        return None