from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import Base

class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    eaten_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="meals")
    dishes = relationship("Dish", back_populates="meal", cascade="all, delete-orphan")

class Dish(Base):
    __tablename__ = "dishes"

    id = Column(Integer, primary_key=True)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    grams = Column(Float, nullable=False)
    calories = Column(Float, nullable=False)
    protein = Column(Float, default=0, nullable=False)
    fat = Column(Float, default=0, nullable=False)
    carbs = Column(Float, default=0, nullable=False)

    meal = relationship("Meal", back_populates="dishes")