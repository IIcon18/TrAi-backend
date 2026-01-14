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

class GenderEnum(str, Enum):
    male = "male"
    female = "female"


class UserCreate(BaseModel):
    """Создание пользователя (упрощённое)"""
    nickname: str
    email: EmailStr
    password: str


class UserRead(BaseModel):
    """Чтение данных пользователя"""
    id: int
    nickname: str
    email: EmailStr
    profile_completed: bool = False
    age: Optional[int] = None
    gender: Optional[GenderEnum] = None
    lifestyle: Optional[LifestyleEnum] = None
    height: Optional[int] = None
    weight: Optional[float] = None
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
    """Обновление профиля пользователя"""
    nickname: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[GenderEnum] = None
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


class ProfileSetup(BaseModel):
    """Дозаполнение профиля после регистрации"""
    age: int
    gender: GenderEnum
    lifestyle: LifestyleEnum
    height: int
    weight: float
    target_weight: Optional[float] = None
    level: Optional[LevelEnum] = LevelEnum.beginner
    weekly_training_goal: Optional[int] = 3