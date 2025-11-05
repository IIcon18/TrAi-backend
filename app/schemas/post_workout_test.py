from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PostWorkoutTestCreate(BaseModel):
    user_id: int
    workout_id: int
    tiredness: int
    mood: int
    energy_level: int
    avg_rest_time: int
    completed_exercises: bool
    pain_discomfort: int
    performance: int
    weight_per_set: float

class PostWorkoutTestRead(BaseModel):
    id: int
    user_id: int
    workout_id: int
    tiredness: int
    mood: int
    energy_level: int
    avg_rest_time: int
    completed_exercises: bool
    pain_discomfort: int
    performance: int
    weight_per_set: float
    recovery_score: float
    created_at: datetime

    class Config:
        from_attributes = True