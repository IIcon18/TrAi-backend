from pydantic import BaseModel, EmailStr
from enum import Enum

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
    token_type: str = "bearer"