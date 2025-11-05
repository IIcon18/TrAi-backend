from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ProgressCreate(BaseModel):
    weight: float
    notes: Optional[str]
    photo: Optional[str]
    total_lifted_weight: Optional[float]
    recovery_score: Optional[float]
    completed_workouts: Optional[int]
    recorded_at: datetime

class ProgressRead(BaseModel):
    id: int
    weight: float
    notes: Optional[str]
    photo: Optional[str]
    total_lifted_weight: Optional[float]
    recovery_score: Optional[float]
    completed_workouts: Optional[int]
    recorded_at: datetime

    class Config:
        from_attributes = True

class ProgressUpdate(BaseModel):
    weight: Optional[float] = None
    notes: Optional[str] = None
    photo: Optional[str] = None
    total_lifted_weight: Optional[float] = None
    recovery_score: Optional[float] = None
    completed_workouts: Optional[int] = None
    recorded_at: Optional[datetime] = None

    class Config:
        from_attributes = True