from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class User(UserBase):
    id: UUID
    role: UserRole
    created_at: datetime
    has_risk_profile: bool = False

    model_config = ConfigDict(from_attributes=True)
