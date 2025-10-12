from pydantic import BaseModel
from typing import Optional, List

class GoalUpdate(BaseModel):
    goal_type: str
    level: str
    days_per_week: int
    training_days: Optional[List[str]] = None