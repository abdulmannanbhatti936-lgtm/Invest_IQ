import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(
        Enum(UserRole, name="userrole"),
        nullable=False,
        default=UserRole.user,
        server_default=UserRole.user.value,
    )
    # Partially-completed questionnaire answers, so onboarding can resume (PRD.md FR6)
    onboarding_progress = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # `risk_profile` is attached as a one-to-one backref by models.risk_profile

    @property
    def has_risk_profile(self) -> bool:
        return getattr(self, "risk_profile", None) is not None


# Emails are stored lowercase (schemas.user.normalize_email); this index also makes the
# database itself reject two addresses that differ only by letter case.
Index("ix_users_email_lower", func.lower(User.email), unique=True)
