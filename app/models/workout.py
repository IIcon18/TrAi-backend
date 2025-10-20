from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from app.core.base import Base

class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="workouts")
    tests = relationship("WorkoutTest", back_populates="workout", cascade="all, delete-orphan")
    exercises = relationship("Exercise", back_populates="workout", cascade="all, delete-orphan")

class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    muscle_group = Column(String, nullable=False)
    sets = Column(Integer, default=3, nullable=False)
    reps = Column(Integer, default=10, nullable=False)
    weight = Column(Float, default=0, nullable=False)
    intensity = Column(String, nullable=True)

    workout = relationship("Workout", back_populates="exercises")