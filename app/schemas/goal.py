from pydantic import BaseModel
from typing import List
from enum import Enum

class GoalType(str, Enum):
    weight_loss = "weight_loss"
    muscle_gain = "muscle_gain"
    maintenance = "maintenance"

class Level(str, Enum):
    beginner = "beginner"
    amateur = "amateur"
    professional = "professional"

class GoalStep1(BaseModel):
    goal_type: GoalType
    level: Level
    training_days_per_week: int

class GoalStep2(BaseModel):
    training_days: List[str]

class GoalUpdate(BaseModel):
    goal_type: GoalType
    level: Level
    training_days_per_week: int
    training_days: List[str]

class GoalResponse(BaseModel):
    id: int
    goal_type: GoalType
    level: Level
    training_days_per_week: int
    training_days: List[str]
    message: str = "Цель успешно обновлена"

    class Config:
        from_attributes = True