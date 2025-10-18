from fastapi import APIRouter
from app.models.dish import Dish, DishGrams

router = APIRouter()

@router.get("/meals")
async def get_meal_types():
    return ["breakfast", "lunch", "dinner", "snack"]

@router.post("/add")
async def add_dish(dish: Dish):
    return {"message": "Блюдо добавлено", "data": dish}

@router.post("/add/grams")
async def add_dish_grams(dish: DishGrams):
    return {"message": "Граммовка добавлена", "data": dish}
