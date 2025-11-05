from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
import logging
import random
from typing import List

from app.core.db import get_db
from app.schemas.dashboard import (
    DashboardResponse, WeeklyProgress, QuickStats, NutritionPlan,
    AIRecommendationRead, EnergyChartData, QuickAction
)
from app.models.user import User
from app.models.workout import Workout, Exercise
from app.models.post_workout_test import PostWorkoutTest
from app.models.ai_recommendation import AIRecommendation
from app.services.nutrition_calculator import NutritionCalculator

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


async def get_energy_chart_data(db: AsyncSession, user_id: int) -> List[EnergyChartData]:
    try:
        tests_result = await db.execute(
            select(PostWorkoutTest)
            .where(PostWorkoutTest.user_id == user_id)
            .order_by(PostWorkoutTest.created_at.desc())
            .limit(7)
        )
        tests = tests_result.scalars().all()

        chart_data = []
        for test in tests:
            chart_data.append(EnergyChartData(
                date=test.created_at.strftime("%d.%m"),
                energy=test.energy_level,
                mood=test.mood
            ))

        if not chart_data:
            demo_dates = [(datetime.utcnow() - timedelta(days=i)).strftime("%d.%m") for i in range(6, -1, -1)]
            for date in demo_dates:
                chart_data.append(EnergyChartData(
                    date=date,
                    energy=random.randint(6, 10),
                    mood=random.randint(6, 10)
                ))

        return chart_data

    except Exception as e:
        logger.error(f"Ошибка в get_energy_chart_data: {e}")
        demo_dates = [(datetime.utcnow() - timedelta(days=i)).strftime("%d.%m") for i in range(6, -1, -1)]
        return [
            EnergyChartData(
                date=date,
                energy=random.randint(6, 10),
                mood=random.randint(6, 10)
            ) for date in demo_dates
        ]


async def get_weekly_progress(db: AsyncSession, user_id: int):
    try:
        user_result = await db.execute(
            select(User.weekly_training_goal)
            .where(User.id == user_id)
        )
        planned_workouts = user_result.scalar() or 0

        week_ago = datetime.utcnow() - timedelta(days=7)
        completed_result = await db.execute(
            select(func.count(Workout.id))
            .where(and_(
                Workout.user_id == user_id,
                Workout.completed == True,
                Workout.scheduled_at >= week_ago
            ))
        )
        completed_workouts = completed_result.scalar() or 0

        completion_rate = 0
        if planned_workouts > 0:
            completion_rate = round((completed_workouts / planned_workouts) * 100, 1)

        return {
            "planned_workouts": planned_workouts,
            "completed_workouts": completed_workouts,
            "completion_rate": completion_rate
        }

    except Exception as e:
        logger.error(f"Ошибка в get_weekly_progress: {e}")
        return {
            "planned_workouts": 0,
            "completed_workouts": 0,
            "completion_rate": 0
        }


async def get_user_nutrition_plan(db: AsyncSession, user_id: int) -> NutritionPlan:
    try:
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return NutritionPlan(
                calories=2000,
                protein=150,
                carbs=200,
                fat=67
            )

        user_calories = NutritionCalculator.get_user_calorie_needs(user)
        user_goal = getattr(user, 'fitness_goal', 'maintenance')
        macros = NutritionCalculator.calculate_macros(user_calories, user_goal)

        return NutritionPlan(
            calories=user_calories,
            protein=macros["protein"],
            carbs=macros["carbs"],
            fat=macros["fat"]
        )

    except Exception as e:
        logger.error(f"Ошибка в расчете БЖУ: {e}")
        return NutritionPlan(
            calories=2000,
            protein=150,
            carbs=200,
            fat=67
        )


async def get_quick_stats(db: AsyncSession, user_id: int) -> QuickStats:
    try:
        weekly_data = await get_weekly_progress(db, user_id)

        week_ago = datetime.utcnow() - timedelta(days=7)
        weight_result = await db.execute(
            select(func.sum(Exercise.weight * Exercise.sets * Exercise.reps))
            .join(Workout)
            .where(and_(
                Workout.user_id == user_id,
                Workout.completed == True,
                Workout.scheduled_at >= week_ago,
                Exercise.exercise_type.in_(["bench_press", "squat", "deadlift"])
            ))
        )
        total_weight_lifted = weight_result.scalar() or 0

        recovery_result = await db.execute(
            select(func.avg(PostWorkoutTest.recovery_score))
            .where(and_(
                PostWorkoutTest.user_id == user_id,
                PostWorkoutTest.created_at >= week_ago
            ))
        )
        recovery_score = recovery_result.scalar() or 75.0

        user_result = await db.execute(
            select(User.initial_weight, User.weight, User.target_weight)
            .where(User.id == user_id)
        )
        user_data = user_result.first()

        goal_progress = 0
        weight_change = 0

        if user_data and user_data.initial_weight and user_data.target_weight:
            initial, current, target = user_data
            weight_change = round(initial - current, 1)

            if target > initial:  # Набор массы
                goal_progress = round(((current - initial) / (target - initial)) * 100, 1)
            elif target < initial:  # Похудение
                goal_progress = round(((initial - current) / (initial - target)) * 100, 1)

        return QuickStats(
            planned_workouts=weekly_data["planned_workouts"],
            total_weight_lifted=round(total_weight_lifted, 1),
            recovery_score=round(recovery_score, 1),
            goal_progress=goal_progress,
            weight_change=weight_change
        )

    except Exception as e:
        logger.error(f"Ошибка в get_quick_stats: {e}")
        return QuickStats(
            planned_workouts=0,
            total_weight_lifted=0,
            recovery_score=75.0,
            goal_progress=0,
            weight_change=0
        )


def generate_progress_fact(quick_stats: QuickStats, weekly_progress: WeeklyProgress, weight_change: float) -> str:
    facts = []

    if weight_change > 0:
        facts.append(f"Ты уже набрал {weight_change} кг мышечной массы! 💪")
    elif weight_change < 0:
        facts.append(f"Ты уже сбросил {abs(weight_change)} кг! Отличный результат! 🎉")

    if weekly_progress.completion_rate >= 80:
        facts.append("Ты выполняешь больше 80% запланированных тренировок - это супер! 🔥")
    elif weekly_progress.completion_rate <= 30:
        facts.append("Попробуй увеличить регулярность тренировок для лучших результатов 📈")

    if quick_stats.recovery_score >= 80:
        facts.append("Твое восстановление на высшем уровне! Продолжай в том же духе 🌟")
    elif quick_stats.recovery_score <= 60:
        facts.append("Обрати внимание на восстановление - это ключ к прогрессу 🛌")

    if quick_stats.total_weight_lifted > 1000:
        facts.append(f"На этой неделе ты поднял {int(quick_stats.total_weight_lifted)} кг - мощно! 💥")

    general_facts = [
        "Каждая тренировка приближает тебя к цели! 🎯",
        "Твое тело становится сильнее с каждым днем 💫",
        "Помни: прогресс - это марафон, а не спринт 🏃‍♂️",
        "Ты создаешь лучшую версию себя каждый день 🌈"
    ]

    if facts:
        return random.choice(facts)
    else:
        return random.choice(general_facts)


def get_quick_actions() -> List[QuickAction]:
    return [
        QuickAction(
            name="Открыть статистику",
            icon="📊",
            route="/progress"
        ),
        QuickAction(
            name="Изменить цель",
            icon="🎯",
            route="/goals"
        ),
        QuickAction(
            name="Начать тренировку",
            icon="💪",
            route="/workouts"
        )
    ]


async def get_ai_recommendations(db: AsyncSession, user_id: int) -> List[AIRecommendationRead]:
    try:
        recommendations_result = await db.execute(
            select(AIRecommendation)
            .where(AIRecommendation.user_id == user_id)
            .order_by(AIRecommendation.created_at.desc())
            .limit(3)
        )
        recommendations = recommendations_result.scalars().all()

        return [AIRecommendationRead.from_orm(rec) for rec in recommendations]

    except Exception as e:
        logger.error(f"Ошибка в get_ai_recommendations: {e}")
        return []


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    try:
        user_result = await db.execute(select(User).order_by(User.id).limit(1))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = user.id

        energy_chart = await get_energy_chart_data(db, user_id)
        weekly_progress_data = await get_weekly_progress(db, user_id)
        nutrition_plan = await get_user_nutrition_plan(db, user_id)
        quick_stats = await get_quick_stats(db, user_id)
        quick_actions = get_quick_actions()
        ai_recommendations = await get_ai_recommendations(db, user_id)

        progress_fact = generate_progress_fact(quick_stats, WeeklyProgress(**weekly_progress_data),
                                               quick_stats.weight_change)

        user_greeting = f"Привет, {user.email.split('@')[0]}!"

        return DashboardResponse(
            user_greeting=user_greeting,
            progress_fact=progress_fact,
            energy_chart=energy_chart,
            weekly_progress=WeeklyProgress(**weekly_progress_data),
            nutrition_plan=nutrition_plan,
            quick_stats=quick_stats,
            quick_actions=quick_actions,
            ai_recommendations=ai_recommendations
        )

    except Exception as e:
        logger.error(f"Ошибка при загрузке dashboard: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при загрузке dashboard: {str(e)}"
        )