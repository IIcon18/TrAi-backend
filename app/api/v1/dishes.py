from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.db import get_db
from app.core.dependencies import get_current_user  # ← ДОБАВИЛ ЗАЩИТУ
from app.schemas.dish import (
    DishCreate, DishResponse, MealCreate, MealResponse,
    SearchDishRequest, DishSearchResult
)
from app.models.meal import Meal, Dish
from app.models.user import User  # ← ДОБАВИЛ ДЛЯ ТИПИЗАЦИИ

router = APIRouter(prefix="/dishes", tags=["dishes"])

DISH_DATABASE = [
    {"id": 1, "name": "Овсяная каша", "calories_per_100g": 88, "protein_per_100g": 3.2, "fat_per_100g": 1.9,
     "carbs_per_100g": 15.0},
    {"id": 2, "name": "Куриная грудка", "calories_per_100g": 165, "protein_per_100g": 31.0, "fat_per_100g": 3.6,
     "carbs_per_100g": 0.0},
    {"id": 3, "name": "Рис отварной", "calories_per_100g": 130, "protein_per_100g": 2.7, "fat_per_100g": 0.3,
     "carbs_per_100g": 28.0},
    {"id": 4, "name": "Яблоко", "calories_per_100g": 52, "protein_per_100g": 0.3, "fat_per_100g": 0.2,
     "carbs_per_100g": 14.0},
    {"id": 5, "name": "Банан", "calories_per_100g": 89, "protein_per_100g": 1.1, "fat_per_100g": 0.3,
     "carbs_per_100g": 22.8},
    {"id": 6, "name": "Творог", "calories_per_100g": 121, "protein_per_100g": 17.0, "fat_per_100g": 5.0,
     "carbs_per_100g": 1.8},
    {"id": 7, "name": "Яйцо куриное", "calories_per_100g": 155, "protein_per_100g": 13.0, "fat_per_100g": 11.0,
     "carbs_per_100g": 1.1},
    {"id": 8, "name": "Гречневая каша", "calories_per_100g": 132, "protein_per_100g": 4.5, "fat_per_100g": 1.3,
     "carbs_per_100g": 27.0},
]


@router.get("/meal-types")
async def get_meal_types():
    """Получить доступные типы приемов пищи"""
    return ["breakfast", "lunch", "dinner", "snack"]


@router.post("/create-meal", response_model=MealResponse)
async def create_meal(
        meal_data: MealCreate,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Создать новый прием пищи"""
    # ИСПОЛЬЗУЕМ current_user.id вместо жесткого user_id = 1 - ДОБАВИЛ ЗАЩИТУ
    user_id = current_user.id

    meal = Meal(
        user_id=user_id,
        type=meal_data.type,
        eaten_at=datetime.utcnow()
    )

    db.add(meal)
    await db.commit()
    await db.refresh(meal)

    return MealResponse(
        id=meal.id,
        user_id=meal.user_id,
        type=meal.type,
        eaten_at=meal.eaten_at,
        dishes=[]
    )


@router.post("/search")
async def search_dishes(search_data: SearchDishRequest):
    """Поиск блюд по названию (пустой запрос возвращает популярные)"""
    query = search_data.query.lower()

    # Если запрос пустой - возвращаем популярные блюда
    if not query.strip():
        results = [DishSearchResult(**dish) for dish in DISH_DATABASE[:6]]
    else:
        # Иначе ищем по названию
        results = [
            DishSearchResult(**dish) for dish in DISH_DATABASE
            if query in dish["name"].lower()
        ]

    return {
        "query": search_data.query,
        "results": results,
        "total_count": len(results)
    }


@router.post("/add-to-meal/{meal_id}", response_model=DishResponse)
async def add_dish_to_meal(
        meal_id: int,
        dish_data: DishCreate,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Добавить блюдо в прием пищи"""
    meal_result = await db.execute(
        select(Meal).where(Meal.id == meal_id)
    )
    meal = meal_result.scalar_one_or_none()

    if not meal:
        raise HTTPException(status_code=404, detail="Прием пищи не найден")

    # ДОБАВИЛ ПРОВЕРКУ - можно добавлять только в свои приемы пищи
    if meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя добавлять блюда в чужие приемы пищи")

    dish = Dish(
        meal_id=meal_id,
        name=dish_data.name,
        grams=dish_data.grams,
        calories=dish_data.calories,
        protein=dish_data.protein,
        fat=dish_data.fat,
        carbs=dish_data.carbs
    )

    db.add(dish)
    await db.commit()
    await db.refresh(dish)

    return DishResponse(
        id=dish.id,
        meal_id=dish.meal_id,
        name=dish.name,
        grams=dish.grams,
        calories=dish.calories,
        protein=dish.protein,
        fat=dish.fat,
        carbs=dish.carbs
    )


@router.get("/meal/{meal_id}", response_model=MealResponse)
async def get_meal_with_dishes(
        meal_id: int,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Получить прием пищи со всеми блюдами"""
    meal_result = await db.execute(
        select(Meal).where(Meal.id == meal_id)
    )
    meal = meal_result.scalar_one_or_none()

    if not meal:
        raise HTTPException(status_code=404, detail="Прием пищи не найден")

    # ДОБАВИЛ ПРОВЕРКУ - можно смотреть только свои приемы пищи
    if meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя просматривать чужие приемы пищи")

    dishes_result = await db.execute(
        select(Dish).where(Dish.meal_id == meal_id)
    )
    dishes = dishes_result.scalars().all()

    return MealResponse(
        id=meal.id,
        user_id=meal.user_id,
        type=meal.type,
        eaten_at=meal.eaten_at,
        dishes=[DishResponse(
            id=dish.id,
            meal_id=dish.meal_id,
            name=dish.name,
            grams=dish.grams,
            calories=dish.calories,
            protein=dish.protein,
            fat=dish.fat,
            carbs=dish.carbs
        ) for dish in dishes]
    )