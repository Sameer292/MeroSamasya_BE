import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Enum, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.schemas.enum import AccountStatusEnum, IssueStatusEnum


class Location(Base):
    __tablename__ = "Locations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    users = relationship("User", back_populates="location")


class User(Base):
    __tablename__ = "Users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    location_id = Column(String, ForeignKey("Locations.id"), nullable=True)
    location = relationship("Location", back_populates="users")
    profile_picture_url = Column(Text, nullable=True)
    account_status = Column(
        Enum(AccountStatusEnum, name="account_status_enum", create_type=False),
        nullable=False,
        default=AccountStatusEnum.active,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    issues = relationship("Issue", back_populates="citizen")


class Issue(Base):
    __tablename__ = "Issues"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    citizen_id = Column(
        String, ForeignKey("Users.id", ondelete="SET NULL"), nullable=False
    )
    category_id = Column(String, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(IssueStatusEnum, name="issue_status_enum", create_type=False),
        nullable=False,
        default=IssueStatusEnum.open,
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    delete_reason = Column(Text, nullable=True)

    citizen = relationship("User", back_populates="issues")
