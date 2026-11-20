import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, Date, DateTime, DDL, Enum, Float, ForeignKey, Index, LargeBinary, String, Text,
    UniqueConstraint, cast, event, func, select,
)
from sqlalchemy.orm import column_property, foreign, relationship
from app.core.database import Base
from app.models.admin_auth import AdminMembership
from app.models.nepal_location_models import LocalLevel
from app.schemas.enum import AccountStatusEnum, IssueStatusEnum, KycStatusEnum, UserRole


def utcnow():
    return datetime.now(timezone.utc)


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
    role = column_property(
        func.coalesce(
            select(AdminMembership.role)
            .where(AdminMembership.user_id == id)
            .correlate_except(AdminMembership)
            .scalar_subquery(),
            UserRole.citizen.value,
        )
    )
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    # ponytail: stores the Nepal LocalLevel id (stringified). Validated
    # against local_levels on write; no legacy Locations table anymore.
    location_id = Column(String, nullable=True)
    location = relationship(
        LocalLevel,
        primaryjoin=foreign(location_id) == cast(LocalLevel.id, String),
        viewonly=True,
    )
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
    upvotes = relationship(
        "Upvote", back_populates="user", cascade="all, delete-orphan"
    )


class Issue(Base):
    __tablename__ = "Issues"
    __table_args__ = (
        Index("ix_issues_citizen_submission", "citizen_id", "submission_id", unique=True),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    citizen_id = Column(
        String, ForeignKey("Users.id", ondelete="SET NULL"), nullable=True
    )
    submission_id = Column(String(36), nullable=True)
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
    # ponytail: area the issue belongs to (LocalLevel id, stringified).
    # Snapshotted from the reporter at creation so /nearme follows the
    # issue, not the reporter's later moves.
    local_level_id = Column(String, nullable=True)
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
    upvotes = relationship(
        "Upvote", back_populates="issue", cascade="all, delete-orphan"
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


class Upvote(Base):
    __tablename__ = "Upvotes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String, ForeignKey("Users.id", ondelete="CASCADE"), nullable=False
    )
    issue_id = Column(
        String, ForeignKey("Issues.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "issue_id", name="unique_user_issue_upvote"),
    )

    user = relationship("User", back_populates="upvotes")
    issue = relationship("Issue", back_populates="upvotes")


class Notification(Base):
    __tablename__ = "Notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String, ForeignKey("Users.id", ondelete="CASCADE"), nullable=False
    )
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    issue_id = Column(String, nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class KycSubmission(Base):
    __tablename__ = "KycSubmissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String, ForeignKey("Users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    full_name = Column(String, nullable=False)
    citizenship_number = Column(String, nullable=False, index=True)
    gender = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    issued_date = Column(Date, nullable=False)
    ward_number = Column(String, nullable=False)
    tole = Column(String, nullable=True)
    province_name = Column(String, nullable=False)
    district_name = Column(String, nullable=False)
    municipality_name = Column(String, nullable=False)
    local_level_id = Column(String, nullable=True)
    # Legacy filenames used to import files from the previous API host.
    selfie_path = Column(Text, nullable=False, default="")
    doc_front_path = Column(Text, nullable=False, default="")
    doc_back_path = Column(Text, nullable=False, default="")
    status = Column(
        Enum(KycStatusEnum, name="kyc_status_enum", create_type=False),
        nullable=False,
        default=KycStatusEnum.pending,
    )
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User")


class KycDocument(Base):
    __tablename__ = "KycDocuments"

    submission_id = Column(
        String, ForeignKey("KycSubmissions.id", ondelete="CASCADE"), primary_key=True
    )
    kind = Column(String, primary_key=True)
    content_type = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)


# Hosted PostgreSQL can grant public API roles access to new tables by default.
event.listen(
    KycDocument.__table__,
    "after_create",
    DDL("ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"),
)
