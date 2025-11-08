from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class MuscleGroup(str, Enum):
    upper_body_push = "upper_body_push"
    upper_body_pull = "upper_body_pull"
    core_stability = "core_stability"
    lower_body = "lower_body"

class Intensity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class ExerciseInput(BaseModel):
    name: str
    muscle_group: str
    sets: int = 3
    reps: int = 10
    weight: float = 0
    intensity: Intensity = Intensity.medium

class WorkoutCreate(BaseModel):
    name: str
    muscle_group: MuscleGroup
    exercises: List[ExerciseInput]

class AIWorkoutRequest(BaseModel):
    muscle_group: MuscleGroup

class ExerciseCompletion(BaseModel):
    id: int
    weight: float
    intensity: Optional[str] = None
    reps: Optional[int] = None

class CompleteWorkoutRequest(BaseModel):
    exercises: List[ExerciseCompletion]

class WorkoutResponse(BaseModel):
    id: int
    name: str
    muscle_group: str
    scheduled_at: datetime
    completed: bool
    total_weight_lifted: float
    ai_generated: bool
    exercises: List[Dict]

    class Config:
        from_attributes = True

class CalendarEvent(BaseModel):
    date: str
    type: str
    title: str
    completed: bool
    muscle_group: Optional[str] = None

class QuickAction(BaseModel):
    name: str
    icon: str
    route: str

class WorkoutPageResponse(BaseModel):
    workout: Optional[WorkoutResponse] = None
    quick_actions: List[QuickAction]
    calendar: List[CalendarEvent]
    reminder: str