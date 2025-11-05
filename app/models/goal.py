import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.core.base import Base

class GoalTypeEnum(str, enum.Enum):
    weight_loss = "weight_loss"
    muscle_gain = "muscle_gain"
    maintenance = "maintenance"
    endurance = "endurance"

class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(Enum(GoalTypeEnum), nullable=False)

    user_goals = relationship("UserGoal", back_populates="goal", cascade="all, delete")

class UserGoal(Base):
    __tablename__ = "user_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    target_weight = Column(Float, nullable=True)
    target_calories = Column(Float, nullable=True)

    user = relationship("User", back_populates="user_goals")
    goal = relationship("Goal", back_populates="user_goals")