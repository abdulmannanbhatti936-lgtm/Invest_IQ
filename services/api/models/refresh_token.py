import uuid

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class RefreshToken(Base):
    """
    One row per issued refresh token (the JWT's `jti`), so tokens can be rotated and revoked
    server-side. Kept in Postgres rather than Redis so revocation never fails open.
    """

    __tablename__ = "refresh_tokens"

    jti = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # Set when the token is used (rotation), on logout, or when reuse is detected
    revoked_at = Column(DateTime(timezone=True), nullable=True)
