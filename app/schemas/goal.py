from pydantic import BaseModel
from typing import Literal

class GoalCreate(BaseModel):
    name: str


class GoalRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class GoalUpdate(BaseModel):
    name: Literal["weight_loss", "muscle_gain", "maintain"]  # только эти 3 варианта

    class Config:
        from_attributes = True


class UserGoalCreate(BaseModel):
    goal_id: int
    target_weight: float
    target_calories: float


class UserGoalRead(BaseModel):
    id: int
    goal_id: int
    target_weight: float
    target_calories: float

    class Config:
        from_attributes = True