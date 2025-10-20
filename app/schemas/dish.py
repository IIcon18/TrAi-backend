from pydantic import BaseModel
from typing import Optional

class Dish(BaseModel):
    name: str
    meal_type: str

class DishGrams(BaseModel):
    name: str
    grams: int