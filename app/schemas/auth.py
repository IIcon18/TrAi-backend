from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class LifestyleEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    age: int
    lifestyle: LifestyleEnum
    height: int
    weight: float

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    user_id: Optional[str] = None