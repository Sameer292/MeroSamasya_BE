import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Enum, ForeignKey, Boolean, UniqueConstraint,Float
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.schemas.enum import AccountStatusEnum, IssueStatusEnum


def utcnow():
    return datetime.now(timezone.utc)


class Location(Base):
    __tablename__ = "Locations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    users = relationship("User", back_populates="location")
    problems = relationship("Problem", back_populates="location")


class Category(Base):
    __tablename__ = "Categories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    icon = Column(String, nullable=False)
    color = Column(String, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    issues = relationship("Issue", back_populates="category")


class User(Base):
    __tablename__ = "Users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    location_id = Column(String, ForeignKey("Locations.id"), nullable=True)
    location = relationship("Location", back_populates="users")
    problems = relationship("Problem", back_populates="user", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="user", cascade="all, delete-orphan")
    profile_picture_url = Column(Text, nullable=True)
    account_status = Column(
        Enum(AccountStatusEnum, name="account_status_enum", create_type=False),
        nullable=False,
        default=AccountStatusEnum.active,
    )
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    issues = relationship("Issue", back_populates="citizen")


class Issue(Base):
    __tablename__ = "Issues"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    citizen_id = Column(
        String, ForeignKey("Users.id", ondelete="SET NULL"), nullable=True
    )
    category_id = Column(
        String, ForeignKey("Categories.id", ondelete="SET NULL"), nullable=True
    )
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
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    delete_reason = Column(Text, nullable=True)

    citizen = relationship("User", back_populates="issues")
    category = relationship("Category", back_populates="issues")
    media = relationship(
        "IssueMedia", back_populates="issue", cascade="all, delete-orphan"
    )


class IssueMedia(Base):
    __tablename__ = "IssueMedia"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    issue_id = Column(
        String, ForeignKey("Issues.id", ondelete="CASCADE"), nullable=False
    )
    url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    issue = relationship("Issue", back_populates="media")


class Problem(Base):
    __tablename__ = "Problems"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    image_url = Column(Text, nullable=True)
    user_id = Column(String, ForeignKey("Users.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(String, ForeignKey("Locations.id"), nullable=True)
    is_resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="problems")
    location = relationship("Location", back_populates="problems")
    votes = relationship("Vote", back_populates="problem", cascade="all, delete-orphan")


class Vote(Base):
    __tablename__ = "Votes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("Users.id", ondelete="CASCADE"), nullable=False)
    problem_id = Column(String, ForeignKey("Problems.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "problem_id", name="unique_user_problem_vote"),
    )

    user = relationship("User", back_populates="votes")
    problem = relationship("Problem", back_populates="votes")