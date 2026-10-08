from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _encode(subject: Any, token_type: str, expires_delta: timedelta, secret: str) -> str:
    now = datetime.now(timezone.utc)
    to_encode = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(to_encode, secret, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode(subject, ACCESS_TOKEN_TYPE, delta, settings.JWT_SECRET)


def create_refresh_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode(subject, REFRESH_TOKEN_TYPE, delta, settings.JWT_REFRESH_SECRET)


def decode_token(token: str, token_type: str) -> str | None:
    """Return the token subject if the token is valid and of the expected type."""
    secret = (
        settings.JWT_REFRESH_SECRET if token_type == REFRESH_TOKEN_TYPE else settings.JWT_SECRET
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != token_type:
        return None
    return payload.get("sub")
