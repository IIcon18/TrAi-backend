from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional, List

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
    initial_weight: Optional[float] = None
    target_weight: Optional[float] = None
    daily_calorie_deficit: Optional[int] = None
    telegram_connected: bool = False
    level: Optional[LevelEnum] = None
    weekly_training_goal: Optional[int] = None
    preferred_training_days: Optional[List[str]] = None
    avatar: Optional[str] = None
    current_goal_id: Optional[int] = None
    ai_calorie_plan: Optional[int] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    age: Optional[int] = None
    lifestyle: Optional[LifestyleEnum] = None
    height: Optional[int] = None
    weight: Optional[float] = None
    target_weight: Optional[float] = None
    daily_calorie_deficit: Optional[int] = None
    level: Optional[LevelEnum] = None
    weekly_training_goal: Optional[int] = None
    preferred_training_days: Optional[List[str]] = None
    current_goal_id: Optional[int] = None
    ai_calorie_plan: Optional[int] = None

    class Config:
        from_attributes = True