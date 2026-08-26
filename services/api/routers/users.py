from fastapi import APIRouter, Depends

from core.deps import get_current_user
from models.user import User
from schemas.user import User as UserSchema

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
