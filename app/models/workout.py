import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Enum
from sqlalchemy.orm import relationship
from app.core.base import Base
from datetime import datetime

class ExerciseTypeEnum(str, enum.Enum):
    bench_press = "bench_press"
    squat = "squat"
    deadlift = "deadlift"
    other = "other"

class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    muscle_group = Column(String, nullable=True)
    scheduled_at = Column(DateTime, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    ai_generated = Column(Boolean, default=False)
    difficulty = Column(String, nullable=True)
    total_weight_lifted = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="workouts")
    tests = relationship("PostWorkoutTest", back_populates="workout", cascade="all, delete-orphan")
    exercises = relationship("Exercise", back_populates="workout", cascade="all, delete-orphan")

class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    equipment = Column(String, nullable=True)
    muscle_group = Column(String, nullable=False)
    sets = Column(Integer, default=3, nullable=False)
    reps = Column(Integer, default=10, nullable=False)
    weight = Column(Float, default=0, nullable=False)
    intensity = Column(String, nullable=True)
    exercise_type = Column(Enum(ExerciseTypeEnum), default="other")
    created_at = Column(DateTime, default=datetime.utcnow)

    workout = relationship("Workout", back_populates="exercises")