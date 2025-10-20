from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import Base

class Progress(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    weight = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    photo = Column(String, nullable=True)  # URL или путь
    total_lifted_weight = Column(Float, default=0, nullable=False)
    recovery_score = Column(Float, default=0, nullable=False)
    completed_workouts = Column(Integer, default=0, nullable=False)
    recorded_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="progress")