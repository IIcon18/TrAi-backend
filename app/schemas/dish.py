from pydantic import BaseModel
from typing import List
from datetime import datetime


class DishBase(BaseModel):
    name: str
    grams: float
    calories: float
    protein: float = 0
    fat: float = 0
    carbs: float = 0


class DishCreate(DishBase):
    meal_type: str

class DishResponse(DishBase):
    id: int
    meal_id: int

    class Config:
        from_attributes = True


class MealCreate(BaseModel):
    type: str


class MealResponse(BaseModel):
    id: int
    user_id: int
    type: str
    eaten_at: datetime
    dishes: List[DishResponse]

    class Config:
        from_attributes = True


class SearchDishRequest(BaseModel):
    query: str


class DishSearchResult(BaseModel):
    id: int
    name: str
    calories_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float