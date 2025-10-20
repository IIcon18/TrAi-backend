import enum
from sqlalchemy import Column, Integer, String, Float, Enum, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import Base

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
    avatar = Column(String, nullable=True)
    telegram_connected = Column(Boolean, default=False)
    level = Column(Enum(LevelEnum), nullable=True)
    weekly_training_goal = Column(Integer, nullable=True)

    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    goal = relationship("Goal", back_populates="user_goals")

    workouts = relationship("Workout", back_populates="user", cascade="all, delete")
    meals = relationship("Meal", back_populates="user", cascade="all, delete")
    progress = relationship("Progress", back_populates="user", cascade="all, delete")