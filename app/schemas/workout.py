from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class WorkoutCreate(BaseModel):
    name: str
    scheduled_at: datetime


class WorkoutRead(BaseModel):
    id: int
    name: str
    scheduled_at: datetime
    completed: bool

    class Config:
        from_attributes = True


class ExerciseCreate(BaseModel):
    name: str
    muscle_group: str
    sets: int
    reps: int
    weight: float
    intensity: Optional[str]


class ExerciseRead(BaseModel):
    id: int
    workout_id: int
    name: str
    muscle_group: str
    sets: int
    reps: int
    weight: float
    intensity: Optional[str]

    class Config:
        from_attributes = True


class WorkoutTestCreate(BaseModel):
    workout_id: int
    q1: int
    q2: int
    q3: int
    q4: int
    q5: int
    q6: int
    q7: int
    q8: int


class WorkoutTestRead(BaseModel):
    id: int
    workout_id: int
    q1: int
    q2: int
    q3: int
    q4: int
    q5: int
    q6: int
    q7: int
    q8: int

    class Config:
        from_attributes = True