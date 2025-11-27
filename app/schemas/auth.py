from pydantic import BaseModel, EmailStr
from typing import Optional, List
from enum import Enum

class LifestyleEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    age: int
    lifestyle: LifestyleEnum
    height: int
    weight: float
    initial_weight: Optional[float] = None
    target_weight: Optional[float] = None
    level: Optional[str] = None
    weekly_training_goal: Optional[int] = None

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str