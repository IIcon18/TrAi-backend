from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class WorkoutCreate(BaseModel):
    name: str
    muscle_group: Optional[str] = None
    scheduled_at: datetime

class WorkoutRead(BaseModel):
    id: int
    name: str
    muscle_group: Optional[str] = None
    scheduled_at: datetime
    completed: bool
    ai_generated: bool = False
    difficulty: Optional[str] = None
    total_weight_lifted: float = 0

    class Config:
        from_attributes = True

class WorkoutUpdate(BaseModel):
    name: Optional[str] = None
    muscle_group: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    completed: Optional[bool] = None
    difficulty: Optional[str] = None
    total_weight_lifted: Optional[float] = None

    class Config:
        from_attributes = True