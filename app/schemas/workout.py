from pydantic import BaseModel, Field
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
    take_post_test: bool = False

class PostWorkoutTestCreate(BaseModel):
    tiredness: int = Field(ge=1, le=10, description="How tired do you feel after this workout? (1-10)")
    mood: int = Field(ge=1, le=10, description="How was your overall mood? (1-10)")
    energy_level: int = Field(ge=1, le=10, description="How was your energy level during the session? (1-10)")
    avg_rest_time: int = Field(ge=30, le=300, description="Average rest time between sets in seconds (30-300)")
    completed_exercises: bool = Field(description="Did you complete all planned exercises?")
    pain_discomfort: int = Field(ge=0, le=10, description="Any pain or discomfort during the workout? (0-10)")
    performance: int = Field(ge=1, le=10, description="How would you rate your performance today? (1-10)")

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

class WorkoutCompleteResponse(WorkoutResponse):
    show_post_test: bool = False

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