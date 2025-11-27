from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from app.models.user import GenderEnum
from app.schemas.goal import GoalResponse

class ProfileBase(BaseModel):
    email: EmailStr
    age: int
    lifestyle: str
    height: int
    weight: float
    level: Optional[str] = None
    weekly_training_goal: Optional[int] = None
    preferred_training_days: Optional[List[str]] = None

class ProfileUpdate(BaseModel):
    age: Optional[int] = None
    gender: Optional[GenderEnum] = None
    lifestyle: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[float] = None
    level: Optional[str] = None
    weekly_training_goal: Optional[int] = None
    preferred_training_days: Optional[List[str]] = None
    target_weight: Optional[float] = None

class AITip(BaseModel):
    tip: str

class AITipsRefreshResponse(BaseModel):
    success: bool
    ai_tips: List[AITip]
    message: str = "AI советы обновлены"

class ProfileResponse(BaseModel):
    id: int
    email: EmailStr
    age: int
    gender: Optional[GenderEnum] = None
    lifestyle: str
    height: int
    weight: float
    initial_weight: Optional[float] = None
    target_weight: Optional[float] = None
    daily_calorie_deficit: Optional[int] = None
    avatar: Optional[str] = None
    telegram_connected: bool = False
    level: Optional[str] = None
    weekly_training_goal: Optional[int] = None
    preferred_training_days: Optional[List[str]] = None
    current_goal: Optional[GoalResponse] = None
    ai_calorie_plan: Optional[int] = None
    created_at: datetime
    ai_tips: List[AITip]

    class Config:
        from_attributes = True

class TelegramConnectRequest(BaseModel):
    telegram_chat_id: str

class TelegramConnectResponse(BaseModel):
    success: bool
    message: str
    telegram_chat_id: Optional[str] = None

class AIFact(BaseModel):
    id: int
    message: str
    created_at: datetime

    class Config:
        from_attributes = True

class AvatarUploadResponse(BaseModel):
    success: bool
    avatar_url: str