from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.schemas.goal import (
    GoalStep1, GoalStep2, GoalUpdate, GoalResponse,
    GoalType, Level
)
from app.models.user import User
from app.models.goal import Goal
from app.services.nutrition_calculator import NutritionCalculator

router = APIRouter(prefix="/goals", tags=["goals"])


async def get_or_create_goal(db: AsyncSession, goal_type: GoalType) -> Goal:
    """Найти или создать цель по типу"""
    goal_result = await db.execute(
        select(Goal).where(Goal.type == goal_type)
    )
    goal = goal_result.scalar_one_or_none()

    if not goal:
        goal = Goal(
            name=goal_type.value.replace("_", " ").title(),
            type=goal_type
        )
        db.add(goal)
        await db.commit()
        await db.refresh(goal)

    return goal


@router.post("/select-goal-type", response_model=dict)
async def update_goal_step1(
        goal_data: GoalStep1,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Обновить цель (шаг 1): тип цели, уровень и дни тренировок"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user.level = goal_data.level
        user.weekly_training_goal = goal_data.training_days_per_week
        goal = await get_or_create_goal(db, goal_data.goal_type)
        user.current_goal_id = goal.id
        user_calories = NutritionCalculator.get_user_calorie_needs(user)
        user.ai_calorie_plan = user_calories

        await db.commit()

        return {
            "success": True,
            "message": "Шаг 1 завершен",
            "training_days_required": goal_data.training_days_per_week,
            "next_step": "step2"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении цели: {str(e)}"
        )


@router.post("/select-training-days", response_model=GoalResponse)
async def update_goal_step2(
        goal_data: GoalStep2,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Обновить цель (шаг 2): выбор конкретных дней для тренировок"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        expected_days = user.weekly_training_goal or 0
        if len(goal_data.training_days) != expected_days:
            raise HTTPException(
                status_code=400,
                detail=f"Выберите ровно {expected_days} дня(ей) для тренировок"
            )

        user.preferred_training_days = goal_data.training_days
        await db.commit()

        goal_result = await db.execute(
            select(Goal).where(Goal.id == user.current_goal_id)
        )
        goal = goal_result.scalar_one_or_none()

        return GoalResponse(
            id=user.id,
            goal_type=goal.type if goal else GoalType.maintenance,
            level=user.level,
            training_days_per_week=user.weekly_training_goal,
            training_days=user.preferred_training_days or [],
            message="🎯 Цель успешно обновлена! Ты на правильном пути! 💪"
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при выборе дней тренировок: {str(e)}"
        )


@router.put("/complete", response_model=GoalResponse)
async def update_goal_complete(
        goal_data: GoalUpdate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Полное обновление цели (все параметры сразу)"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if len(goal_data.training_days) != goal_data.training_days_per_week:
            raise HTTPException(
                status_code=400,
                detail=f"Количество выбранных дней должно быть {goal_data.training_days_per_week}"
            )

        goal = await get_or_create_goal(db, goal_data.goal_type)

        user.level = goal_data.level
        user.weekly_training_goal = goal_data.training_days_per_week
        user.preferred_training_days = goal_data.training_days
        user.current_goal_id = goal.id

        user_calories = NutritionCalculator.get_user_calorie_needs(user)
        user.ai_calorie_plan = user_calories

        await db.commit()

        return GoalResponse(
            id=user.id,
            goal_type=goal_data.goal_type,
            level=goal_data.level,
            training_days_per_week=goal_data.training_days_per_week,
            training_days=goal_data.training_days,
            message="🎯 Цель успешно обновлена! Ты на правильном пути! 💪"
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении цели: {str(e)}"
        )


@router.get("/current", response_model=GoalResponse)
async def get_current_goal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить текущую цель пользователя"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        goal = None
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            goal = goal_result.scalar_one_or_none()

        return GoalResponse(
            id=user.id,
            goal_type=goal.type if goal else GoalType.maintenance,
            level=user.level or Level.beginner,
            training_days_per_week=user.weekly_training_goal or 0,
            training_days=user.preferred_training_days or [],
            message="Текущая цель"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении цели: {str(e)}"
        )