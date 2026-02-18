from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserAdminRead(BaseModel):
    id: int
    nickname: str
    email: str
    role: str
    profile_completed: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RoleUpdateRequest(BaseModel):
    role: str  # "user", "pro", "admin"


class RoleUpdateResponse(BaseModel):
    message: str
    user_id: int
    new_role: str
