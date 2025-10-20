from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional

class LifestyleEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class LevelEnum(str, Enum):
    beginner = "beginner"
    amateur = "amateur"
    professional = "professional"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    age: int
    lifestyle: LifestyleEnum
    height: int
    weight: float

class UserRead(BaseModel):
    id: int
    email: EmailStr
    age: int
    lifestyle: LifestyleEnum
    height: int
    weight: float
    goal_id: Optional[int] = None

    class Config:
        from_attributes = True