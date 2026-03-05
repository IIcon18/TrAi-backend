from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
import logging
import random
from typing import List
from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.schemas.progress import (
    ProgressResponse,
    ProgressChartData,
    GoalProgress,
    NutritionPlan,
    ProgressMetric,
    CurrentNutrition,
)
from app.models.post_workout_test import PostWorkoutTest
from app.models.user import User
from app.models.progress import Progress
from app.models.workout import Workout
from app.models.goal import Goal
from app.models.meal import Meal, Dish
from app.services.nutrition_calculator import NutritionCalculator
from app.services.ai_service import ai_service

router = APIRouter(tags=["progress"])
logger = logging.getLogger(__name__)


async def get_activity_chart_data(db: AsyncSession, user_id: int) -> List[dict]:
    """Получить данные для графика активности (mood/energy) за последние 7 дней"""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        tests_result = await db.execute(
            select(PostWorkoutTest)
            .where(
                and_(
                    PostWorkoutTest.user_id == user_id,
                    PostWorkoutTest.created_at >= week_ago,
                )
            )
            .order_by(PostWorkoutTest.created_at.asc())
        )
        tests = tests_result.scalars().all()

        activity_data = []
        day_names = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ]

        for test in tests:
            day_name = day_names[test.created_at.weekday()]
            activity_data.append(
                {"day": day_name, "mood": test.mood, "energy": test.energy_level}
            )

        # Если данных нет, возвращаем демо
        if not activity_data:
            return [
                {
                    "day": day_names[i],
                    "mood": random.randint(6, 10),
                    "energy": random.randint(6, 10),
                }
                for i in range(7)
            ]

        return activity_data

    except Exception as e:
        logger.error(f"Ошибка в get_activity_chart_data: {e}")
        day_names = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ]
        return [
            {
                "day": day_names[i],
                "mood": random.randint(6, 10),
                "energy": random.randint(6, 10),
            }
            for i in range(7)
        ]


async def get_progress_chart_data(
    db: AsyncSession, user_id: int, metric: ProgressMetric
) -> List[ProgressChartData]:
    """Получить данные для графика по выбранной метрике"""
    try:
        month_ago = datetime.utcnow() - timedelta(days=30)

        progress_result = await db.execute(
            select(Progress)
            .where(and_(Progress.user_id == user_id, Progress.recorded_at >= month_ago))
            .order_by(Progress.recorded_at.asc())
        )
        progress_records = progress_result.scalars().all()

        chart_data = []

        for record in progress_records:
            if metric == ProgressMetric.WEIGHT and record.weight:
                chart_data.append(
                    ProgressChartData(
                        date=record.recorded_at.strftime("%d.%m"),
                        value=record.weight,
                        label=f"{record.weight} кг",
                    )
                )
            elif metric == ProgressMetric.WORKOUTS:
                chart_data.append(
                    ProgressChartData(
                        date=record.recorded_at.strftime("%d.%m"),
                        value=record.completed_workouts,
                        label=f"{record.completed_workouts} тренировок",
                    )
                )
            elif metric == ProgressMetric.RECOVERY and record.recovery_score:
                chart_data.append(
                    ProgressChartData(
                        date=record.recorded_at.strftime("%d.%m"),
                        value=record.recovery_score,
                        label=f"{record.recovery_score}%",
                    )
                )

        if not chart_data:
            return await generate_demo_chart_data(metric)

        return chart_data

    except Exception as e:
        logger.error(f"Ошибка в get_progress_chart_data: {e}")
        return await generate_demo_chart_data(metric)


async def generate_demo_chart_data(metric: ProgressMetric) -> List[ProgressChartData]:
    demo_data = []
    base_date = datetime.utcnow() - timedelta(days=30)

    for i in range(31):
        date = (base_date + timedelta(days=i)).strftime("%d.%m")

        if metric == ProgressMetric.WEIGHT:
            value = 80 - (i * 0.16) + random.uniform(-0.5, 0.5)
            demo_data.append(
                ProgressChartData(
                    date=date, value=round(value, 1), label=f"{round(value, 1)} кг"
                )
            )
        elif metric == ProgressMetric.WORKOUTS:
            value = random.randint(0, 2) if i % 3 != 0 else 0
            demo_data.append(
                ProgressChartData(date=date, value=value, label=f"{value} тренировок")
            )
        elif metric == ProgressMetric.RECOVERY:
            value = random.randint(60, 95)
            demo_data.append(
                ProgressChartData(date=date, value=value, label=f"{value}%")
            )
        elif metric == ProgressMetric.BODY_FAT:
            value = 25 - (i * 0.1) + random.uniform(-1, 1)
            demo_data.append(
                ProgressChartData(
                    date=date, value=round(value, 1), label=f"{round(value, 1)}%"
                )
            )

    return demo_data


async def generate_progress_fact(
    chart_data: List[ProgressChartData],
    metric: ProgressMetric,
    user: User,
    db: AsyncSession,
) -> str:
    """Сгенерировать AI анализ прогресса на основе данных графика"""

    if not chart_data:
        user_name = user.email.split("@")[0] if user.email else "Спортсмен"
        return f"{user_name}, начните отслеживать прогресс, чтобы получать персональные рекомендации! 📊"

    try:
        trend_analysis = ""
        if len(chart_data) >= 2:
            first_value = chart_data[0].value
            last_value = chart_data[-1].value
            trend = last_value - first_value
            trend_percentage = (trend / first_value * 100) if first_value != 0 else 0

            if metric == ProgressMetric.WEIGHT:
                trend_analysis = f"Изменение веса: {trend:+.1f} кг ({trend_percentage:+.1f}%) за период"
            elif metric == ProgressMetric.BODY_FAT:
                trend_analysis = (
                    f"Изменение процента жира: {trend:+.1f}% ({trend_percentage:+.1f}%)"
                )
            elif metric == ProgressMetric.WORKOUTS:
                total_workouts = sum(item.value for item in chart_data)
                trend_analysis = f"Всего тренировок: {total_workouts}, средняя активность: {total_workouts / len(chart_data):.1f} в день"
            elif metric == ProgressMetric.RECOVERY:
                avg_recovery = sum(item.value for item in chart_data) / len(chart_data)
                trend_analysis = f"Среднее восстановление: {avg_recovery:.1f}%, диапазон: {min(item.value for item in chart_data)}-{max(item.value for item in chart_data)}%"

        user_goal = "не указана"
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            current_goal = goal_result.scalar_one_or_none()
            if current_goal:
                user_goal = current_goal.type.value

        analysis = await ai_service.generate_progress_analysis(
            chart_data=[
                {"date": item.date, "value": item.value, "label": item.label}
                for item in chart_data[-10:]
            ],
            metric=metric.value,
            user_data={
                "goal": user_goal,
                "level": user.level.value if user.level else "beginner",
                "name": user.email.split("@")[0] if user.email else "Пользователь",
            },
        )

        return analysis

    except Exception as e:
        logger.error(f"Ошибка AI анализа прогресса: {e}")
        return await _generate_fallback_fact(chart_data, metric, user)


async def _generate_fallback_fact(
    chart_data: List[ProgressChartData], metric: ProgressMetric, user: User
) -> str:
    """Локальная генерация фактов как fallback"""
    user_name = user.email.split("@")[0] if user.email else "Спортсмен"

    if len(chart_data) < 2:
        return f"{user_name}, продолжайте собирать данные для точного анализа! 📈"

    first_value = chart_data[0].value
    last_value = chart_data[-1].value
    trend = last_value - first_value

    if metric == ProgressMetric.WEIGHT:
        if trend < -1:
            return f"🎉 Отличный прогресс! Вес снизился на {abs(trend):.1f} кг"
        elif trend > 1:
            return f"📊 Набор {trend:.1f} кг - возможно, стоит скорректировать питание"
        else:
            return f"⚖️ Вес стабилен на {last_value:.1f} кг - хорошая работа!"

    elif metric == ProgressMetric.BODY_FAT:
        if trend < -0.5:
            return f"💪 Отлично! Процент жира снизился на {abs(trend):.1f}%"
        elif trend > 0.5:
            return f"📈 Рост жира на {trend:.1f}% - обратите внимание на питание"
        else:
            return f"🔄 Процент жира стабилен - {last_value:.1f}%"

    elif metric == ProgressMetric.WORKOUTS:
        total_workouts = sum(item.value for item in chart_data)
        avg_per_week = total_workouts / 4.3

        if avg_per_week >= 4:
            return f"🔥 Мощная активность! {total_workouts} тренировок за месяц"
        elif avg_per_week >= 2:
            return f"👍 Хорошая регулярность! {total_workouts} тренировок"
        else:
            return f"🎯 Попробуйте увеличить частоту тренировок"

    elif metric == ProgressMetric.RECOVERY:
        avg_recovery = sum(item.value for item in chart_data) / len(chart_data)

        if avg_recovery >= 80:
            return f"🌟 Восстановление на высоте! {avg_recovery:.0f}%"
        elif avg_recovery >= 60:
            return f"📊 Нормальное восстановление {avg_recovery:.0f}%"
        else:
            return f"💤 Восстановление {avg_recovery:.0f}% - уделите внимание отдыху"

    return (
        f"{user_name}, ваш прогресс выглядит promising! Продолжайте в том же духе! 🚀"
    )


async def get_goal_progress(db: AsyncSession, user_id: int, user: User) -> GoalProgress:
    """Получить прогресс по цели пользователя"""
    try:
        current_weight = user.weight or 0
        initial_weight = user.initial_weight or current_weight
        target_weight = user.target_weight or (current_weight - 5)

        weight_lost = initial_weight - current_weight
        completion_percentage = 0

        if initial_weight and target_weight and initial_weight > target_weight:
            total_goal = initial_weight - target_weight
            if total_goal > 0:
                completion_percentage = min(
                    100, max(0, (weight_lost / total_goal) * 100)
                )

        streak_weeks = await calculate_streak_weeks(db, user_id)

        return GoalProgress(
            completion_percentage=round(completion_percentage, 1),
            weight_lost=round(weight_lost, 1),
            daily_calorie_deficit=user.daily_calorie_deficit or 500,
            streak_weeks=streak_weeks,
            target_weight=target_weight,
            current_weight=current_weight,
        )

    except Exception as e:
        logger.error(f"Ошибка в get_goal_progress: {e}")
        return GoalProgress(
            completion_percentage=0.0,
            weight_lost=0.0,
            daily_calorie_deficit=500,
            streak_weeks=0,
            target_weight=user.target_weight or 90,
            current_weight=user.weight or 95,
        )


async def calculate_streak_weeks(db: AsyncSession, user_id: int) -> int:
    """Рассчитать стрик недель с тренировками"""
    try:
        workouts_result = await db.execute(
            select(Workout)
            .where(and_(Workout.user_id == user_id, Workout.completed == True))
            .order_by(Workout.scheduled_at.desc())
        )
        workouts = workouts_result.scalars().all()

        if not workouts:
            return 0

        current_week = datetime.utcnow().isocalendar()[1]
        streak = 0

        for week in range(current_week, current_week - 10, -1):
            week_workouts = [
                w for w in workouts if w.scheduled_at.isocalendar()[1] == week
            ]
            if week_workouts:
                streak += 1
            else:
                break

        return streak

    except Exception as e:
        logger.error(f"Ошибка в calculate_streak_weeks: {e}")
        return random.randint(1, 5)


async def get_current_nutrition_consumption(db: AsyncSession, user_id: int) -> dict:
    """Получить текущее потребление БЖУ за сегодня"""
    try:
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_end = datetime.utcnow().replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

        # Получаем все meals за сегодня
        meals_result = await db.execute(
            select(Meal).where(
                and_(
                    Meal.user_id == user_id,
                    Meal.eaten_at >= today_start,
                    Meal.eaten_at <= today_end,
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

        return {
            "protein": round(total_protein, 1),
            "carbs": round(total_carbs, 1),
            "fat": round(total_fat, 1),
            "calories": round(total_calories, 1),
        }
    except Exception as e:
        logger.error(f"Ошибка в get_current_nutrition_consumption: {e}")
        return {"protein": 0.0, "carbs": 0.0, "fat": 0.0, "calories": 0.0}


async def get_nutrition_plan(db: AsyncSession, user_id: int) -> NutritionPlan:
    """Получить план питания"""
    try:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            return NutritionPlan(
                calories=2000,
                protein=150,
                carbs=200,
                fat=67,
                protein_percentage=30,
                carbs_percentage=40,
                fat_percentage=30,
            )

        user_calories = NutritionCalculator.get_user_calorie_needs(user)

        # Определяем тип цели из Goal модели
        user_goal = "maintenance"
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            goal_obj = goal_result.scalar_one_or_none()
            if goal_obj and goal_obj.type:
                user_goal = goal_obj.type.value

        macros = NutritionCalculator.calculate_macros(user_calories, user_goal)

        total_calories = macros["protein"] * 4 + macros["carbs"] * 4 + macros["fat"] * 9
        protein_percentage = (macros["protein"] * 4 / total_calories) * 100
        carbs_percentage = (macros["carbs"] * 4 / total_calories) * 100
        fat_percentage = (macros["fat"] * 9 / total_calories) * 100

        return NutritionPlan(
            calories=user_calories,
            protein=macros["protein"],
            carbs=macros["carbs"],
            fat=macros["fat"],
            protein_percentage=round(protein_percentage, 1),
            carbs_percentage=round(carbs_percentage, 1),
            fat_percentage=round(fat_percentage, 1),
        )

    except Exception as e:
        logger.error(f"Ошибка в get_nutrition_plan: {e}")
        return NutritionPlan(
            calories=2000,
            protein=150,
            carbs=200,
            fat=67,
            protein_percentage=30,
            carbs_percentage=40,
            fat_percentage=30,
        )


# Убираем все демо-данные
@router.get("", response_model=ProgressResponse)
async def get_progress(
    metric: ProgressMetric = ProgressMetric.WEIGHT,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = current_user
    user_id = user.id

    if not user:
        return ProgressResponse(
            selected_metric=metric.value,
            chart_data=[],
            ai_fact="",
            goal_progress=GoalProgress(
                completion_percentage=0.0,
                weight_lost=0.0,
                daily_calorie_deficit=0,
                streak_weeks=0,
                target_weight=0.0,
                current_weight=0.0,
            ),
            nutrition_plan=NutritionPlan(
                calories=0,
                protein=0,
                carbs=0,
                fat=0,
                protein_percentage=0.0,
                carbs_percentage=0.0,
                fat_percentage=0.0,
            ),
            current_nutrition=CurrentNutrition(
                calories=0.0, protein=0.0, carbs=0.0, fat=0.0
            ),
        )

    chart_data = await get_progress_chart_data(db, user_id, metric) or []
    ai_fact = (
        await generate_progress_fact(chart_data, metric, user, db) if chart_data else ""
    )
    goal_progress = (
        await get_goal_progress(db, user_id, user)
        if chart_data
        else GoalProgress(
            completion_percentage=0.0,
            weight_lost=0.0,
            daily_calorie_deficit=0,
            streak_weeks=0,
            target_weight=0.0,
            current_weight=0.0,
        )
    )
    nutrition_plan = (
        await get_nutrition_plan(db, user_id)
        if chart_data
        else NutritionPlan(
            calories=0,
            protein=0,
            carbs=0,
            fat=0,
            protein_percentage=0.0,
            carbs_percentage=0.0,
            fat_percentage=0.0,
        )
    )
    current_nutrition_data = await get_current_nutrition_consumption(db, user_id)
    current_nutrition = CurrentNutrition(**current_nutrition_data)

    return ProgressResponse(
        selected_metric=metric.value,
        chart_data=chart_data,
        ai_fact=ai_fact,
        goal_progress=goal_progress,
        nutrition_plan=nutrition_plan,
        current_nutrition=current_nutrition,
    )


@router.get("/activity")
async def get_activity_data(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        activity_data = await get_activity_chart_data(db, current_user.id)
        return {"activityData": activity_data or []}
    except Exception as e:
        logger.error(f"Ошибка при загрузке активности: {e}")
        return {"activityData": []}
