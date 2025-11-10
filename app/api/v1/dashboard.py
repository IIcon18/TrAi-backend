from fastapi import APIRouter, Depends
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
    """Получить данные для графика энергии и настроения за последние 7 дней"""
    try:
        # Получаем послетренировочные тесты за последнюю неделю
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

        # Если данных нет - генерируем демо-данные
        if not chart_data:
            demo_dates = [(datetime.utcnow() - timedelta(days=i)).strftime("%d.%m") for i in range(6, -1, -1)]
            for date in demo_dates:
                chart_data.append(EnergyChartData(
                    date=date,
                    energy=random.randint(6, 10),
                    mood=random.randint(6, 10)
                ))

        return chart_data[::-1]  # Переворачиваем чтобы старые даты были первыми

    except Exception as e:
        logger.error(f"Ошибка в get_energy_chart_data: {e}")
        # Возвращаем демо-данные при ошибке
        demo_dates = [(datetime.utcnow() - timedelta(days=i)).strftime("%d.%m") for i in range(6, -1, -1)]
        return [
            EnergyChartData(
                date=date,
                energy=random.randint(6, 10),
                mood=random.randint(6, 10)
            ) for date in demo_dates
        ]


async def get_weekly_progress(db: AsyncSession, user_id: int):
    """Получить прогресс тренировок за последнюю неделю"""
    try:
        # Получаем плановое количество тренировок пользователя
        user_result = await db.execute(
            select(User.weekly_training_goal)
            .where(User.id == user_id)
        )
        planned_workouts = user_result.scalar() or 0

        # Считаем завершенные тренировки за последние 7 дней
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

        # Рассчитываем процент выполнения
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
    """Получить план питания пользователя"""
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

        # Рассчитываем калории и БЖУ на основе данных пользователя
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
    """Получить быструю статистику для дашборда"""
    try:
        weekly_data = await get_weekly_progress(db, user_id)

        # Считаем общий поднятый вес за неделю (только базовые упражнения)
        week_ago = datetime.utcnow() - timedelta(days=7)

        exercises_result = await db.execute(
            select(Exercise)
            .join(Workout)
            .where(and_(
                Workout.user_id == user_id,
                Workout.completed == True,
                Workout.scheduled_at >= week_ago,
                Exercise.exercise_type.in_(["bench_press", "squat", "deadlift"])
            ))
            .order_by(Exercise.created_at.desc())
        )
        exercises = exercises_result.scalars().all()

        # Берем максимальный вес по каждому упражнению за период
        exercise_max_weights = {}
        for exercise in exercises:
            if exercise.exercise_type not in exercise_max_weights:
                total_weight = exercise.weight * exercise.sets * exercise.reps
                exercise_max_weights[exercise.exercise_type] = total_weight

        total_weight_lifted = sum(exercise_max_weights.values())

        # Получаем средний показатель восстановления
        recovery_result = await db.execute(
            select(func.avg(PostWorkoutTest.recovery_score))
            .where(and_(
                PostWorkoutTest.user_id == user_id,
                PostWorkoutTest.created_at >= week_ago
            ))
        )
        recovery_score = recovery_result.scalar() or 75.0

        # Рассчитываем прогресс по цели веса
        user_result = await db.execute(
            select(User.initial_weight, User.weight, User.target_weight, User.fitness_goal)
            .where(User.id == user_id)
        )
        user_data = user_result.first()

        goal_progress = 0
        weight_change = 0
        target_progress = "0 кг"

        if user_data and user_data.initial_weight and user_data.target_weight:
            initial, current, target, goal = user_data
            weight_change = round(initial - current, 1)

            # Форматируем строку цели
            if target > initial:
                target_progress = f"+{target - initial} кг"
            elif target < initial:
                target_progress = f"-{initial - target} кг"
            else:
                target_progress = "0 кг"

            # Рассчитываем процент выполнения цели
            if target > initial:  # набор массы
                total_change_needed = target - initial
                current_progress = current - initial
                if total_change_needed > 0:
                    goal_progress = round((current_progress / total_change_needed) * 100, 1)
            elif target < initial:  # похудение
                total_change_needed = initial - target
                current_progress = initial - current
                if total_change_needed > 0:
                    goal_progress = round((current_progress / total_change_needed) * 100, 1)

        return QuickStats(
            planned_workouts=weekly_data["planned_workouts"],
            total_weight_lifted=round(total_weight_lifted, 1),
            recovery_score=round(recovery_score, 1),
            goal_progress=max(0, min(100, goal_progress)),  # Ограничиваем 0-100%
            weight_change=weight_change,
            target_progress=target_progress
        )

    except Exception as e:
        logger.error(f"Ошибка в get_quick_stats: {e}")
        return QuickStats(
            planned_workouts=0,
            total_weight_lifted=0,
            recovery_score=75.0,
            goal_progress=0,
            weight_change=0,
            target_progress="0 кг"
        )


def generate_progress_fact(quick_stats: QuickStats, weekly_progress: WeeklyProgress, weight_change: float) -> str:
    """Сгенерировать мотивирующий факт на основе статистики"""
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

    # Общие мотивирующие фразы
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
    """Получить список быстрых действий для дашборда"""
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
    """Получить последние AI рекомендации для пользователя"""
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
    """Получить все данные для главного дашборда"""
    try:
        # Получаем первого пользователя (для демо)
        user_result = await db.execute(select(User).order_by(User.id).limit(1))
        user = user_result.scalar_one_or_none()
        if not user:
            return await get_demo_dashboard()

        user_id = user.id

        # Параллельно собираем все данные для дашборда
        energy_chart = await get_energy_chart_data(db, user_id)
        weekly_progress_data = await get_weekly_progress(db, user_id)
        nutrition_plan = await get_user_nutrition_plan(db, user_id)
        quick_stats = await get_quick_stats(db, user_id)
        quick_actions = get_quick_actions()
        ai_recommendations = await get_ai_recommendations(db, user_id)

        # Генерируем персонализированный факт прогресса
        progress_fact = generate_progress_fact(quick_stats, WeeklyProgress(**weekly_progress_data),
                                               quick_stats.weight_change)

        # Формируем приветствие
        user_greeting = f"Привет, {user.email.split('@')[0]}!" if user.email else "Привет!"

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
        return await get_demo_dashboard()


async def get_demo_dashboard() -> DashboardResponse:
    """Вернуть демо-данные дашборда когда нет пользователя"""
    demo_dates = [(datetime.utcnow() - timedelta(days=i)).strftime("%d.%m") for i in range(6, -1, -1)]

    return DashboardResponse(
        user_greeting="Привет!",
        progress_fact="Начни тренировки чтобы увидеть свой прогресс! 🚀",
        energy_chart=[
            EnergyChartData(date=date, energy=random.randint(6, 10), mood=random.randint(6, 10))
            for date in demo_dates
        ],
        weekly_progress=WeeklyProgress(
            planned_workouts=4,
            completed_workouts=3,
            completion_rate=75.0
        ),
        nutrition_plan=NutritionPlan(
            calories=2000,
            protein=150,
            carbs=200,
            fat=67
        ),
        quick_stats=QuickStats(
            planned_workouts=4,
            total_weight_lifted=1250.5,
            recovery_score=82.0,
            goal_progress=25.0,
            weight_change=-2.0,
            target_progress="-8 кг"
        ),
        quick_actions=get_quick_actions(),
        ai_recommendations=[]
    )