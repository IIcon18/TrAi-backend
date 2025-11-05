from pydantic import BaseModel
from datetime import datetime

class AIRecommendationRead(BaseModel):
    id: int
    type: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True