from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.user import UserRole
from schemas.types import UTCDateTime


def normalize_email(value: str) -> str:
    """Emails are matched case-insensitively: always store and look them up trimmed + lowercase."""
    return value.strip().lower()


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(max_length=120)

    @field_validator("email", mode="before")
    @classmethod
    def email_lowercase(cls, v: object) -> object:
        return normalize_email(v) if isinstance(v, str) else v

    # Runs before the length check, so whitespace never counts towards the minimum
    @field_validator("full_name", mode="before")
    @classmethod
    def full_name_trimmed(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


# bcrypt only uses the first 72 bytes of a password; anything longer would be silently
# ignored, so two long passwords sharing their first 72 bytes would both log in.
MAX_PASSWORD_BYTES = 72
MIN_FULL_NAME_LENGTH = 2


class UserCreate(UserBase):
    # Same rule as the web register form: at least 2 characters after trimming.
    # Input only: stored names are returned as they are.
    full_name: str = Field(min_length=MIN_FULL_NAME_LENGTH, max_length=120)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password is too long: the maximum is {MAX_PASSWORD_BYTES} bytes "
                "(72 English characters; fewer if it contains Urdu or other non-English characters)"
            )
        return v


class User(UserBase):
    id: UUID
    role: UserRole
    created_at: UTCDateTime
    has_risk_profile: bool = False

    model_config = ConfigDict(from_attributes=True)
