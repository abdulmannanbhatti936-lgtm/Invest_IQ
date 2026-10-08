from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from core.config import settings
from models.refresh_token import RefreshToken


def create_refresh_token_record(db: Session, user_id: UUID) -> RefreshToken:
    """Record a new refresh token; the caller signs a JWT carrying its `jti`. Not committed."""
    record = RefreshToken(
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(record)
    db.flush()
    return record


def get_refresh_token_record(db: Session, jti: UUID) -> RefreshToken | None:
    return db.get(RefreshToken, jti)


def revoke_if_active(db: Session, jti: UUID) -> bool:
    """
    Revoke one token if it is still active. Returns False if it was already revoked.
    A single conditional UPDATE, so two requests racing with the same token can't both win.
    """
    updated = (
        db.query(RefreshToken)
        .filter(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    )
    return updated == 1


def revoke_all_for_user(db: Session, user_id: UUID) -> int:
    return (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    )
