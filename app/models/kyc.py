import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Enum, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.schemas.enum import KYCStatusEnum


def utcnow():
    return datetime.now(timezone.utc)


class KYCSubmission(Base):
    __tablename__ = "KYCSubmissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(
        String,
        ForeignKey("Users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    full_name          = Column(String(200), nullable=False)
    date_of_birth      = Column(Date, nullable=False)
    citizenship_number = Column(String(100), nullable=False, unique=True)

    citizenship_front_url = Column(Text, nullable=False)
    citizenship_back_url  = Column(Text, nullable=False)
    selfie_url            = Column(Text, nullable=False)

    status = Column(
        Enum(KYCStatusEnum, name="kyc_status_enum", create_type=False),
        nullable=False,
        default=KYCStatusEnum.pending,
    )
    rejection_reason = Column(Text, nullable=True)
    reviewed_by      = Column(
        String, ForeignKey("Users.id", ondelete="SET NULL"), nullable=True
    )

    submitted_at = Column(DateTime(timezone=True), default=utcnow)
    reviewed_at  = Column(DateTime(timezone=True), nullable=True)

    user     = relationship("User", foreign_keys=[user_id], back_populates="kyc")
    reviewer = relationship("User", foreign_keys=[reviewed_by])