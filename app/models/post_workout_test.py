from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.base import Base
from datetime import datetime

class PostWorkoutTest(Base):
    __tablename__ = "post_workout_tests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=True, index=True)
    tiredness = Column(Integer, nullable=False)
    mood = Column(Integer, nullable=False)
    energy_level = Column(Integer, nullable=False)
    avg_rest_time = Column(Integer, nullable=False)
    completed_exercises = Column(Boolean, nullable=False)
    pain_discomfort = Column(Integer, nullable=False)
    performance = Column(Integer, nullable=False)
    weight_per_set = Column(Float, nullable=False)
    recovery_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    workout = relationship("Workout", back_populates="tests")