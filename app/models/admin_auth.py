from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AdminMembership(Base):
    __tablename__ = "AdminMemberships"
    __table_args__ = (CheckConstraint("role IN ('admin', 'superadmin')"),)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("Users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16))


class AdminSession(Base):
    __tablename__ = "AdminSessions"

    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("Users.id", ondelete="CASCADE"), index=True
    )
    access_expires_at: Mapped[int] = mapped_column(BigInteger)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
