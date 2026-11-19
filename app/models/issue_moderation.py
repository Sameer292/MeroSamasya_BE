from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IssueModerationEvent(Base):
    __tablename__ = "IssueModerationEvents"
    __table_args__ = (Index("ix_issue_moderation_history", "issue_id", "created_at", "id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    issue_id: Mapped[str] = mapped_column(ForeignKey("Issues.id", ondelete="CASCADE"))
    reviewer_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changes: Mapped[list[dict[str, str | None]]] = mapped_column(JSON)
