from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RefreshToken(Base):
    __tablename__ = "RefreshTokens"

    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Older rows get a session ID when their refresh token is first rotated.
    session_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("Users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[int] = mapped_column(BigInteger)
