import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Enum
from app.core.database import Base
import enum

class RoleEnum(str, enum.Enum):
    citizen = "citizen"
    admin = "admin"
    superadmin = "superadmin"

class AccountStatusEnum(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    deleted = "deleted"

class User(Base):
    __tablename__ = "Users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    role = Column(Enum(RoleEnum, name="user_role_enum", create_type=False), nullable=False, default=RoleEnum.citizen)
    profile_picture_url = Column(Text, nullable=True)
    account_status = Column(Enum(AccountStatusEnum, name="account_status_enum", create_type=False), nullable=False, default=AccountStatusEnum.active)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)