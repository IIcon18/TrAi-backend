from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, any_
from datetime import datetime

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.core.rbac import require_pro
from app.schemas.dish import (
    DishCreate, DishResponse, MealCreate, MealResponse,
    SearchDishRequest, DishSearchResult, AnalyzeDishRequest
)
from app.models.meal import Meal, Dish
from app.models.user import User
from app.services.nutrition_service import nutrition_service
from app.services.ai_service import ai_service
from app.services.openfoodfacts_service import openfoodfacts_service

router = APIRouter(tags=["dishes"])

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
async def get_meal_types(current_user: User = Depends(require_pro)):
    """Получить доступные типы приемов пищи (только pro/admin)"""
    return ["breakfast", "lunch", "dinner", "snack"]


@router.post("/create-meal", response_model=MealResponse)
async def create_meal(
        meal_data: MealCreate,
        current_user: User = Depends(require_pro),
        db: AsyncSession = Depends(get_db)
):
    """Создать новый прием пищи"""
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
async def search_dishes(
        search_data: SearchDishRequest,
        current_user: User = Depends(require_pro),
        db: AsyncSession = Depends(get_db)
):
    """Поиск блюд по названию в базе продуктов + AI если не найдено"""
    from app.models.product import Product

    query = search_data.query.lower().strip()

    if not query:
        # Возвращаем популярные продукты
        result = await db.execute(
            select(Product)
            .where(Product.verified == True)
            .order_by(Product.id)
            .limit(10)
        )
        products = result.scalars().all()
    else:
        # 1) Поиск по name_lower (LIKE)
        # 2) Поиск по name_variants (ANY в массиве)
        # Разбиваем запрос на слова для более гибкого поиска
        words = query.split()

        conditions = [
            # Полное совпадение подстроки в name_lower
            Product.name_lower.like(f"%{query}%"),
        ]

        # Поиск по каждому слову отдельно (для запросов типа "курица" -> "куриная грудка")
        for word in words:
            if len(word) >= 3:
                conditions.append(Product.name_lower.like(f"%{word}%"))

        # Поиск по массиву name_variants — любой вариант содержит запрос
        # PostgreSQL: query = ANY(name_variants)
        conditions.append(
            func.array_to_string(Product.name_variants, ' ').ilike(f"%{query}%")
        )
        for word in words:
            if len(word) >= 3:
                conditions.append(
                    func.array_to_string(Product.name_variants, ' ').ilike(f"%{word}%")
                )

        result = await db.execute(
            select(Product).where(or_(*conditions)).limit(20)
        )
        products = result.scalars().all()

        # Если ничего не найдено в базе - пробуем OpenFoodFacts
        if not products:
            try:
                print(f"🌍 Trying OpenFoodFacts for: {search_data.query}")
                off_products = await openfoodfacts_service.search_products(
                    query=search_data.query,
                    language="ru",
                    limit=10
                )

                if off_products:
                    print(f"✅ Found {len(off_products)} products in OpenFoodFacts")
                    # Конвертируем в формат DishSearchResult
                    results = [
                        DishSearchResult(
                            id=0,  # Временный ID (из внешнего API)
                            name=p["name"],
                            calories_per_100g=p["calories_per_100g"],
                            protein_per_100g=p["protein_per_100g"],
                            fat_per_100g=p["fat_per_100g"],
                            carbs_per_100g=p["carbs_per_100g"]
                        ) for p in off_products
                    ]

                    # Опционально: сохраняем первый результат в нашу базу
                    if off_products and len(off_products) > 0:
                        best_match = off_products[0]
                        # Создаем новый продукт в базе
                        new_product = Product(
                            name=best_match["name"],
                            name_lower=best_match["name"].lower(),
                            name_variants=[search_data.query.lower()],
                            calories_per_100g=best_match["calories_per_100g"],
                            protein_per_100g=best_match["protein_per_100g"],
                            fat_per_100g=best_match["fat_per_100g"],
                            carbs_per_100g=best_match["carbs_per_100g"],
                            category="external",
                            verified=False,
                            source="openfoodfacts"
                        )
                        db.add(new_product)
                        await db.commit()
                        print(f"💾 Saved to database: {best_match['name']}")

                    return {
                        "query": search_data.query,
                        "results": results,
                        "total_count": len(results),
                        "source": "openfoodfacts"
                    }
            except Exception as e:
                print(f"❌ OpenFoodFacts search failed: {e}")

        # Если OpenFoodFacts тоже не помог - попробуем AI
        if not products:
            try:
                print(f"🤖 Trying AI for: {search_data.query}")
                nutrition = await nutrition_service.get_nutrition(
                    dish_name=search_data.query,
                    grams=100,
                    db=db,
                    ai_service=ai_service
                )
                # Создаем временный результат с AI данными
                results = [{
                    "id": 0,  # Временный ID
                    "name": search_data.query,
                    "calories_per_100g": nutrition["calories"],
                    "protein_per_100g": nutrition["protein"],
                    "fat_per_100g": nutrition["fat"],
                    "carbs_per_100g": nutrition["carbs"]
                }]
                return {
                    "query": search_data.query,
                    "results": results,
                    "total_count": 1,
                    "source": "ai"
                }
            except Exception as e:
                print(f"❌ AI search failed: {e}")
                # Возвращаем пустой результат
                return {
                    "query": search_data.query,
                    "results": [],
                    "total_count": 0
                }

    results = [
        DishSearchResult(
            id=p.id,
            name=p.name,
            calories_per_100g=p.calories_per_100g,
            protein_per_100g=p.protein_per_100g,
            fat_per_100g=p.fat_per_100g,
            carbs_per_100g=p.carbs_per_100g
        ) for p in products
    ]

    return {
        "query": search_data.query,
        "results": results,
        "total_count": len(results),
        "source": "database"
    }


@router.post("/analyze")
async def analyze_dish_with_ai(
        search_data: AnalyzeDishRequest,
        current_user: User = Depends(require_pro),
        db: AsyncSession = Depends(get_db)
):
    """
    Анализ блюда через AI (если не найдено в базе).
    Использует NutritionService с fallback цепочкой.
    """
    dish_name = search_data.query.strip()
    grams = search_data.grams

    if not dish_name:
        raise HTTPException(status_code=400, detail="Название блюда не может быть пустым")

    try:
        # Используем NutritionService для поиска в базе/кеше или вызова AI
        nutrition = await nutrition_service.get_nutrition(
            dish_name=dish_name,
            grams=grams,
            db=db,
            ai_service=ai_service
        )

        return {
            "dish_name": dish_name,
            "grams": grams,
            "nutrition": nutrition,
            "source": ai_service.last_used_provider or "database"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось проанализировать блюдо: {str(e)}"
        )


@router.post("/add-to-meal/{meal_id}", response_model=DishResponse)
async def add_dish_to_meal(
        meal_id: int,
        dish_data: DishCreate,
        current_user: User = Depends(require_pro),
        db: AsyncSession = Depends(get_db)
):
    """Добавить блюдо в прием пищи"""
    meal_result = await db.execute(
        select(Meal).where(Meal.id == meal_id)
    )
    meal = meal_result.scalar_one_or_none()

    if not meal:
        raise HTTPException(status_code=404, detail="Прием пищи не найден")

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
        current_user: User = Depends(require_pro),
        db: AsyncSession = Depends(get_db)
):
    """Получить прием пищи со всеми блюдами"""
    meal_result = await db.execute(
        select(Meal).where(Meal.id == meal_id)
    )
    meal = meal_result.scalar_one_or_none()

    if not meal:
        raise HTTPException(status_code=404, detail="Прием пищи не найден")
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