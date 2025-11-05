from pydantic import BaseModel

class Dish(BaseModel):
    name: str
    meal_type: str

class DishGrams(BaseModel):
    name: str
    grams: int