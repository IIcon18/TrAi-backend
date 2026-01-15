from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
import logging
import random
from typing import List, Dict, Any

from app.core.db import get_db
from app.schemas.dashboard import (
    DashboardResponse, WeeklyProgress, QuickStats, NutritionPlan,
    CurrentNutrition, AIRecommendationRead, EnergyChartData, QuickAction
)
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.workout import Workout, Exercise
from app.models.post_workout_test import PostWorkoutTest
from app.models.ai_recommendation import AIRecommendation
from app.models.goal import Goal
from app.models.meal import Meal, Dish
from app.services.nutrition_calculator import NutritionCalculator
from app.services.ai_service import ai_service

router = APIRouter(tags=["dashboard"])
logger = logging.getLogger(__name__)


async def get_last_workout_info(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Получить информацию о последней тренировке"""
    try:
        workout_result = await db.execute(
            select(Workout)
            .where(and_(
                Workout.user_id == user_id,
                Workout.completed == True
            ))
            .order_by(Workout.scheduled_at.desc())
        )
        last_workout = workout_result.scalars().first()

        if last_workout:
            return {
                'date': last_workout.scheduled_at.strftime("%d.%m"),
                'type': last_workout.workout_type or 'тренировка',
                'duration': getattr(last_workout, 'duration', 60)
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка получения последней тренировки: {e}")
        return None


async def get_energy_chart_data(db: AsyncSession, user_id: int) -> List[EnergyChartData]:
    """Получить данные для графика энергии и настроения за последние 7 дней"""
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
                date=test.created_at.isoformat(),
                energy=test.energy_level,
                mood=test.mood
            ))

        if not chart_data:
            for i in range(6, -1, -1):
                date_obj = datetime.utcnow() - timedelta(days=i)
                chart_data.append(EnergyChartData(
                    date=date_obj.isoformat(),
                    energy=random.randint(6, 10),
                    mood=random.randint(6, 10)
                ))

        return chart_data[::-1]

    except Exception as e:
        logger.error(f"Ошибка в get_energy_chart_data: {e}")
        result = []
        for i in range(6, -1, -1):
            date_obj = datetime.utcnow() - timedelta(days=i)
            result.append(EnergyChartData(
                date=date_obj.isoformat(),
                energy=random.randint(6, 10),
                mood=random.randint(6, 10)
            ))
        return result


async def get_weekly_progress(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Получить прогресс тренировок за последнюю неделю"""
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


async def get_current_nutrition_consumption(db: AsyncSession, user_id: int) -> CurrentNutrition:
    """Получить текущее потребление БЖУ за сегодня"""
    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Получаем все meals за сегодня
        meals_result = await db.execute(
            select(Meal)
            .where(
                and_(
                    Meal.user_id == user_id,
                    Meal.eaten_at >= today_start,
                    Meal.eaten_at <= today_end
                )
            )
        )
        meals = meals_result.scalars().all()
        
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0
        total_calories = 0.0
        
        # Суммируем БЖУ из всех dishes всех meals за сегодня
        for meal in meals:
            dishes_result = await db.execute(
                select(Dish).where(Dish.meal_id == meal.id)
            )
            dishes = dishes_result.scalars().all()
            
            for dish in dishes:
                total_protein += dish.protein or 0
                total_carbs += dish.carbs or 0
                total_fat += dish.fat or 0
                total_calories += dish.calories or 0
        
        return CurrentNutrition(
            protein=round(total_protein, 1),
            carbs=round(total_carbs, 1),
            fat=round(total_fat, 1),
            calories=round(total_calories, 1)
        )
    except Exception as e:
        logger.error(f"Ошибка в get_current_nutrition_consumption: {e}")
        return CurrentNutrition(
            protein=0.0,
            carbs=0.0,
            fat=0.0,
            calories=0.0
        )


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

        user_calories = NutritionCalculator.get_user_calorie_needs(user)
        user_goal = getattr(user, 'level', 'maintenance')
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

        exercise_max_weights = {}
        for exercise in exercises:
            if exercise.exercise_type not in exercise_max_weights:
                total_weight = exercise.weight * exercise.sets * exercise.reps
                exercise_max_weights[exercise.exercise_type] = total_weight

        total_weight_lifted = sum(exercise_max_weights.values())

        recovery_result = await db.execute(
            select(func.avg(PostWorkoutTest.recovery_score))
            .where(and_(
                PostWorkoutTest.user_id == user_id,
                PostWorkoutTest.created_at >= week_ago
            ))
        )
        recovery_score = recovery_result.scalar() or 75.0

        user_result = await db.execute(
            select(User.initial_weight, User.weight, User.target_weight, User.level)
            .where(User.id == user_id)
        )
        user_data = user_result.first()

        goal_progress = 0
        weight_change = 0
        target_progress = "0 кг"

        if user_data and user_data.initial_weight and user_data.target_weight:
            initial, current, target, level = user_data
            weight_change = round(initial - current, 1)

            if target > initial:
                target_progress = f"+{target - initial} кг"
            elif target < initial:
                target_progress = f"-{initial - target} кг"
            else:
                target_progress = "0 кг"

            if target > initial:
                total_change_needed = target - initial
                current_progress = current - initial
                if total_change_needed > 0:
                    goal_progress = round((current_progress / total_change_needed) * 100, 1)
            elif target < initial:
                total_change_needed = initial - target
                current_progress = initial - current
                if total_change_needed > 0:
                    goal_progress = round((current_progress / total_change_needed) * 100, 1)

        return QuickStats(
            planned_workouts=weekly_data["planned_workouts"],
            total_weight_lifted=round(total_weight_lifted, 1),
            recovery_score=round(recovery_score, 1),
            goal_progress=max(0, min(100, goal_progress)),
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


async def generate_ai_greeting(
        db: AsyncSession,
        user_id: int,
        quick_stats: QuickStats,
        weekly_progress: Dict[str, Any],
        energy_chart: List[EnergyChartData]
) -> str:
    """Сгенерировать AI приветствие для дашборда"""
    try:
        # Получаем данные пользователя вместе с целью - БЕЗОПАСНЫЙ JOIN
        user_result = await db.execute(
            select(User.email, User.level, Goal.name)
            .select_from(User)
            .outerjoin(Goal, User.current_goal_id == Goal.id)
            .where(User.id == user_id)
        )
        user_data = user_result.first()

        if not user_data:
            return "Привет! Начни тренировки чтобы увидеть свой прогресс! 🚀"

        user_email, user_level, user_goal_name = user_data
        user_name = user_email.split('@')[0] if user_email else "Спортсмен"

        user_info = {
            'name': user_name,
            'level': user_level or 'beginner',
            'goal': user_goal_name or 'general_fitness'
        }

        # Получаем информацию о последней тренировке
        last_workout = await get_last_workout_info(db, user_id)

        # Преобразуем energy chart data
        energy_data = [
            {'energy': item.energy, 'mood': item.mood, 'date': item.date}
            for item in energy_chart
        ]

        print(f"🎯 Generating AI greeting for user: {user_name}")
        print(f"🎯 User info: {user_info}")
        print(f"🎯 Quick stats: {quick_stats.dict()}")
        print(f"🎯 Weekly progress: {weekly_progress}")

        # Генерируем AI приветствие
        greeting = await ai_service.generate_dashboard_greeting(
            user_data=user_info,
            quick_stats=quick_stats.dict(),
            weekly_progress=weekly_progress,
            energy_data=energy_data,
            last_workout=last_workout
        )

        print(f"🎯 AI Greeting generated: {greeting}")
        return greeting

    except Exception as e:
        logger.error(f"Ошибка генерации AI приветствия: {e}")
        user_result = await db.execute(
            select(User.email).where(User.id == user_id)
        )
        user = user_result.first()
        user_name = user.email.split('@')[0] if user else "Спортсмен"
        return f"Привет, {user_name}! Рад видеть тебя! 💪"


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получить все данные для главного дашборда"""
    try:
        user_id = current_user.id

        # Параллельно собираем все данные для дашборда
        energy_chart = await get_energy_chart_data(db, user_id)
        weekly_progress_data = await get_weekly_progress(db, user_id)
        nutrition_plan = await get_user_nutrition_plan(db, user_id)
        current_nutrition = await get_current_nutrition_consumption(db, user_id)
        quick_stats = await get_quick_stats(db, user_id)
        quick_actions = get_quick_actions()
        ai_recommendations = await get_ai_recommendations(db, user_id)

        # Получаем информацию о последней тренировке
        last_workout = await get_last_workout_info(db, user_id)

        # Генерируем AI сообщения
        progress_fact = await generate_ai_greeting(
            db, user_id, quick_stats, weekly_progress_data, energy_chart
        )
        last_training_message = await ai_service.generate_last_training_message(last_workout)
        
        # Преобразуем QuickStats в словарь для AI функции
        quick_stats_dict = {
            'total_weight_lifted': quick_stats.total_weight_lifted,
            'recovery_score': quick_stats.recovery_score,
            'goal_progress': quick_stats.goal_progress,
            'weight_change': quick_stats.weight_change
        }
        weekly_progress_message = await ai_service.generate_weekly_progress_message(
            weekly_progress_data, 
            quick_stats_dict
        )

        user_greeting = f"Привет, {current_user.email.split('@')[0]}!" if current_user.email else "Привет!"

        return DashboardResponse(
            user_greeting=user_greeting,
            progress_fact=progress_fact,
            last_training_message=last_training_message,
            weekly_progress_message=weekly_progress_message,
            energy_chart=energy_chart,
            weekly_progress=WeeklyProgress(**weekly_progress_data),
            nutrition_plan=nutrition_plan,
            current_nutrition=current_nutrition,
            quick_stats=quick_stats,
            quick_actions=quick_actions,
            ai_recommendations=ai_recommendations
        )

    except Exception as e:
        logger.error(f"Ошибка при загрузке dashboard: {str(e)}")
        # При ошибке все равно пытаемся сгенерировать AI приветствие
        try:
            progress_fact = await generate_ai_greeting(
                db, current_user.id,
                QuickStats(
                    planned_workouts=0,
                    total_weight_lifted=0,
                    recovery_score=75.0,
                    goal_progress=0,
                    weight_change=0,
                    target_progress="0 кг"
                ),
                {"planned_workouts": 0, "completed_workouts": 0, "completion_rate": 0},
                []
            )
        except:
            progress_fact = "Начни тренировки чтобы увидеть свой прогресс! 🚀"

        return await get_demo_dashboard(current_user, progress_fact)


async def get_demo_dashboard(user: User = None, progress_fact: str = None) -> DashboardResponse:
    """Вернуть демо-данные дашборда для нового пользователя или при ошибках"""
    if user and user.email:
        user_greeting = f"Привет, {user.email.split('@')[0]}!"
        if not progress_fact:
            progress_fact = f"{user.email.split('@')[0]}, начни тренировки чтобы увидеть свой прогресс! 🚀"
    else:
        user_greeting = "Привет!"
        if not progress_fact:
            progress_fact = "Начни тренировки чтобы увидеть свой прогресс! 🚀"

    demo_chart_data = []
    for i in range(6, -1, -1):
        date_obj = datetime.utcnow() - timedelta(days=i)
        demo_chart_data.append(EnergyChartData(
            date=date_obj.isoformat(),
            energy=random.randint(6, 10),
            mood=random.randint(6, 10)
        ))

    return DashboardResponse(
        user_greeting=user_greeting,
        progress_fact=progress_fact,
        last_training_message="Your last training was upper body push yesterday 💪",
        weekly_progress_message="Отличная неделя! Продолжай в том же духе! 🔥",
        energy_chart=demo_chart_data,
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
        current_nutrition=CurrentNutrition(
            calories=0.0,
            protein=0.0,
            carbs=0.0,
            fat=0.0
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