from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import Base
from datetime import datetime

class PostWorkoutTest(Base):
    __tablename__ = "post_workout_tests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=True, index=True)
    energy_level = Column(Integer, nullable=False)
    mood = Column(Integer, nullable=False)
    muscle_soreness = Column(Integer, nullable=False)
    sleep_quality = Column(Integer, nullable=False)
    appetite = Column(Integer, nullable=False)
    motivation = Column(Integer, nullable=False)
    focus = Column(Integer, nullable=False)
    overall_condition = Column(Integer, nullable=False)
    recovery_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="workout_tests")
    workout = relationship("Workout")