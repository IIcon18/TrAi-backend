import enum
from sqlalchemy import Column, Integer, String, Float, Enum, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from app.core.base import Base
from datetime import datetime

class LifestyleEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class LevelEnum(str, enum.Enum):
    beginner = "beginner"
    amateur = "amateur"
    professional = "professional"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    lifestyle = Column(Enum(LifestyleEnum), nullable=False)
    height = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    target_weight = Column(Float, nullable=True)
    avatar = Column(String, nullable=True)
    telegram_connected = Column(Boolean, default=False)
    telegram_chat_id = Column(String, nullable=True)
    level = Column(Enum(LevelEnum), nullable=True)
    weekly_training_goal = Column(Integer, nullable=True)
    preferred_training_days = Column(JSON, nullable=True)
    current_goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    ai_calorie_plan = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    current_goal = relationship("Goal", foreign_keys=[current_goal_id])
    goals = relationship("UserGoal", back_populates="user", cascade="all, delete")
    workouts = relationship("Workout", back_populates="user", cascade="all, delete")
    meals = relationship("Meal", back_populates="user", cascade="all, delete")
    progress = relationship("Progress", back_populates="user", cascade="all, delete")
    workout_tests = relationship("PostWorkoutTest", back_populates="user", cascade="all, delete")
    ai_recommendations = relationship("AIRecommendation", back_populates="user", cascade="all, delete")