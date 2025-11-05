from pydantic import BaseModel
from enum import Enum
from typing import Optional


class GoalTypeEnum(str, Enum):
    weight_loss = "weight_loss"
    muscle_gain = "muscle_gain"
    maintenance = "maintenance"
    endurance = "endurance"


class GoalBase(BaseModel):
    name: str
    type: GoalTypeEnum


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[GoalTypeEnum] = None


class GoalResponse(GoalBase):
    id: int

    class Config:
        from_attributes = True


class UserGoalBase(BaseModel):
    target_weight: Optional[float] = None
    target_calories: Optional[float] = None


class UserGoalCreate(UserGoalBase):
    user_id: int
    goal_id: int


class UserGoalResponse(UserGoalBase):
    id: int
    user_id: int
    goal_id: int

    class Config:
        from_attributes = True