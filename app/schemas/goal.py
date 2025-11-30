from pydantic import BaseModel
from typing import List
import enum
from app.models.goal import GoalTypeEnum

class Level(str, enum.Enum):
    beginner = "beginner"
    amateur = "amateur"
    professional = "professional"

class GoalStep1(BaseModel):
    goal_type: GoalTypeEnum
    level: Level
    training_days_per_week: int

class GoalStep2(BaseModel):
    training_days: List[str]

class GoalUpdate(BaseModel):
    goal_type: GoalTypeEnum
    level: Level
    training_days_per_week: int
    training_days: List[str]

class GoalResponse(BaseModel):
    id: int
    goal_type: GoalTypeEnum
    level: Level
    training_days_per_week: int
    training_days: List[str]
    message: str = "Цель успешно обновлена"

    class Config:
        from_attributes = True