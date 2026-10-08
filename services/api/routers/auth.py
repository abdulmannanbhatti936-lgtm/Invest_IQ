import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.rate_limit import auth_rate_limit
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from crud.refresh_token import (
    create_refresh_token_record,
    get_refresh_token_record,
    revoke_all_for_user,
    revoke_if_active,
)
from crud.user import create_user, get_user_by_email
from models.user import User
from schemas.auth import Token
from schemas.user import User as UserSchema
from schemas.user import UserCreate


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# bcrypt hash of a throwaway string (same cost factor as real hashes). Checked when the
# email is unknown so that path costs the same as a wrong password, and response time
# doesn't reveal which emails are registered.
_DUMMY_PASSWORD_HASH = "$2b$12$9uI56Mz9tujzkTpjogk8POJW8UGYqmRBm6OLyiDujoEEDQOyW1PbK"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(auth_rate_limit)])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _issue_tokens(db: Session, user: User) -> dict:
    """New access + refresh pair; the refresh token is recorded so it can be rotated/revoked."""
    record = create_refresh_token_record(db, user_id=user.id)
    db.commit()
    return {
        "access_token": create_access_token(subject=user.email),
        "refresh_token": create_refresh_token(subject=user.email, jti=record.jti),
        "token_type": "bearer",
    }


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    return create_user(db, user_in=user_in)


@router.post("/login", response_model=Token)
def login(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(db, email=form_data.username)
    password_ok = verify_password(
        form_data.password, user.password_hash if user else _DUMMY_PASSWORD_HASH
    )
    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=Token)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Rotation: every refresh token works once. Using it revokes it and returns a new pair.
    Presenting an already-revoked token means it was copied (or replayed), so every refresh
    token of that user is revoked and they must log in again (reuse detection).
    """
    claims = decode_refresh_token(request.refresh_token)
    if claims is None:
        raise _INVALID_CREDENTIALS
    email, jti = claims
    user = get_user_by_email(db, email=email)
    record = get_refresh_token_record(db, jti)
    if user is None or record is None or record.user_id != user.id:
        raise _INVALID_CREDENTIALS

    if not revoke_if_active(db, jti):
        revoked = revoke_all_for_user(db, user.id)
        db.commit()
        logger.warning(
            "Refresh token reuse detected for user %s: revoked %d active token(s)", user.id, revoked
        )
        raise _INVALID_CREDENTIALS

    return _issue_tokens(db, user)  # commits the revocation together with the new record


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: RefreshTokenRequest, db: Session = Depends(get_db)) -> Response:
    """
    Revoke the given refresh token. Always 204, so logging out never fails on the client and
    the response says nothing about the token. (Access tokens are short-lived and stateless:
    they stay valid until they expire, at most ACCESS_TOKEN_EXPIRE_MINUTES.)
    """
    claims = decode_refresh_token(request.refresh_token)
    if claims is not None:
        revoke_if_active(db, claims[1])
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
