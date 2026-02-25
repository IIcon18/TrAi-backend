import enum
from sqlalchemy import Column, Integer, String, Float, Enum, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from app.core.base import Base
from datetime import datetime


class RoleEnum(str, enum.Enum):
    user = "user"
    pro = "pro"
    admin = "admin"


class LifestyleEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class LevelEnum(str, enum.Enum):
    beginner = "beginner"
    amateur = "amateur"
    professional = "professional"


class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    profile_completed = Column(Boolean, default=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.user, nullable=False)
    ai_workout_uses = Column(Integer, default=0, nullable=False)
    ai_workout_reset_date = Column(DateTime, nullable=True)


    age = Column(Integer, nullable=True)
    gender = Column(Enum(GenderEnum), nullable=True)
    lifestyle = Column(Enum(LifestyleEnum), nullable=True)
    height = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    initial_weight = Column(Float, nullable=True)
    target_weight = Column(Float, nullable=True)
    daily_calorie_deficit = Column(Integer, nullable=True)
    avatar = Column(String, nullable=True)
    telegram_connected = Column(Boolean, default=False)
    telegram_chat_id = Column(String, nullable=True)
    level = Column(Enum(LevelEnum), nullable=True)
    weekly_training_goal = Column(Integer, nullable=True)
    preferred_training_days = Column(JSON, nullable=True)
    current_goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    ai_calorie_plan = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    refresh_token = Column(String, nullable=True)
    refresh_token_expires = Column(DateTime, nullable=True)

    current_goal = relationship("Goal", foreign_keys=[current_goal_id])
    user_goals = relationship("UserGoal", back_populates="user", cascade="all, delete")
    workouts = relationship("Workout", back_populates="user", cascade="all, delete")
    meals = relationship("Meal", back_populates="user", cascade="all, delete")
    progress = relationship("Progress", back_populates="user", cascade="all, delete")
    ai_recommendations = relationship("AIRecommendation", back_populates="user", cascade="all, delete")