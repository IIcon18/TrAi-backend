from pydantic import BaseModel
from typing import List
from datetime import datetime


class DishCreate(BaseModel):
    name: str
    grams: float
    calories: float
    protein: float
    fat: float
    carbs: float


class DishRead(BaseModel):
    id: int
    meal_id: int
    name: str
    grams: float
    calories: float
    protein: float
    fat: float
    carbs: float

    class Config:
        from_attributes = True


class MealCreate(BaseModel):
    type: str
    eaten_at: datetime


class MealRead(BaseModel):
    id: int
    type: str
    eaten_at: datetime
    dishes: List[DishRead] = []

    class Config:
        from_attributes = True