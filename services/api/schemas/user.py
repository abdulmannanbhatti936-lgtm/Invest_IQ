from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.user import UserRole
from schemas.types import UTCDateTime


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)


# bcrypt only uses the first 72 bytes of a password; anything longer would be silently
# ignored, so two long passwords sharing their first 72 bytes would both log in.
MAX_PASSWORD_BYTES = 72


class UserCreate(UserBase):
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
