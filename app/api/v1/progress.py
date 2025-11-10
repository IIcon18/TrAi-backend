from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
import logging
import random
from typing import List

from app.core.db import get_db
from app.schemas.progress import (
    ProgressResponse, ProgressChartData, GoalProgress, NutritionPlan, ProgressMetric
)
from app.models.user import User
from app.models.progress import Progress
from app.models.workout import Workout
from app.services.nutrition_calculator import NutritionCalculator

router = APIRouter(prefix="/progress", tags=["progress"])
logger = logging.getLogger(__name__)


async def get_progress_chart_data(
        db: AsyncSession,
        user_id: int,
        metric: ProgressMetric
) -> List[ProgressChartData]:
    """Получить данные для графика по выбранной метрике"""
    try:
        # Получаем записи прогресса за последние 30 дней
        month_ago = datetime.utcnow() - timedelta(days=30)

        progress_result = await db.execute(
            select(Progress)
            .where(and_(
                Progress.user_id == user_id,
                Progress.recorded_at >= month_ago
            ))
            .order_by(Progress.recorded_at.asc())
        )
        progress_records = progress_result.scalars().all()

        chart_data = []

        for record in progress_records:
            if metric == ProgressMetric.WEIGHT and record.weight:
                chart_data.append(ProgressChartData(
                    date=record.recorded_at.strftime("%d.%m"),
                    value=record.weight,
                    label=f"{record.weight} кг"
                ))
            elif metric == ProgressMetric.WORKOUTS:
                chart_data.append(ProgressChartData(
                    date=record.recorded_at.strftime("%d.%m"),
                    value=record.completed_workouts,
                    label=f"{record.completed_workouts} тренировок"
                ))
            elif metric == ProgressMetric.RECOVERY and record.recovery_score:
                chart_data.append(ProgressChartData(
                    date=record.recorded_at.strftime("%d.%m"),
                    value=record.recovery_score,
                    label=f"{record.recovery_score}%"
                ))

        # Если данных нет, генерируем демо-данные
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
            demo_data.append(ProgressChartData(
                date=date,
                value=round(value, 1),
                label=f"{round(value, 1)} кг"
            ))
        elif metric == ProgressMetric.WORKOUTS:
            value = random.randint(0, 2) if i % 3 != 0 else 0
            demo_data.append(ProgressChartData(
                date=date,
                value=value,
                label=f"{value} тренировок"
            ))
        elif metric == ProgressMetric.RECOVERY:
            value = random.randint(60, 95)
            demo_data.append(ProgressChartData(
                date=date,
                value=value,
                label=f"{value}%"
            ))
        elif metric == ProgressMetric.BODY_FAT:
            value = 25 - (i * 0.1) + random.uniform(-1, 1)
            demo_data.append(ProgressChartData(
                date=date,
                value=round(value, 1),
                label=f"{round(value, 1)}%"
            ))

    return demo_data


async def generate_progress_fact(
        chart_data: List[ProgressChartData],
        metric: ProgressMetric,
        user: User
) -> str:

    if not chart_data:
        user_name = user.email.split('@')[0] if user.email else "Спортсмен"
        return f"{user_name}, начните отслеживать прогресс, чтобы получать персональные рекомендации! 📊"

    # Получаем имя пользователя для персонализации
    user_name = user.email.split('@')[0] if user.email else "Вы"

    # Анализируем тренд
    trend = 0
    if len(chart_data) >= 2:
        first_value = chart_data[0].value
        last_value = chart_data[-1].value
        trend = last_value - first_value

    facts = []

    if metric == ProgressMetric.WEIGHT:
        if trend < -2:
            facts.extend([
                f"{user_name}, отличный результат! Вы сбросили {abs(trend):.1f} кг за месяц! 🎉",
                f"Ваш вес уверенно снижается - минус {abs(trend):.1f} кг за 30 дней! 💪",
                f"{user_name}, прекрасный прогресс! {abs(trend):.1f} кг ближе к цели! 🌟"
            ])
        elif trend > 2:
            facts.extend([
                f"{user_name}, набор {trend:.1f} кг за месяц - возможно, стоит скорректировать питание 📊",
                f"Обратите внимание на динамику веса: +{trend:.1f} кг за 30 дней 🏋️‍♂️"
            ])
        else:
            current_weight = chart_data[-1].value if chart_data else user.weight
            facts.extend([
                f"{user_name}, вес стабилен на {current_weight:.1f} кг - отличная работа! ⚖️",
                f"Стабильность веса {current_weight:.1f} кг - признак мастерства! 📈"
            ])

    elif metric == ProgressMetric.WORKOUTS:
        total_workouts = sum(item.value for item in chart_data)
        avg_per_week = total_workouts / 4.3
        user_level = getattr(user, 'level', 'beginner')

        if avg_per_week >= 4:
            level_comment = "как профессионал" if user_level == "professional" else "на продвинутом уровне"
            facts.extend([
                f"{user_name}, впечатляющая активность! {total_workouts} тренировок за месяц 🔥",
                f"Вы тренируетесь {level_comment}! {total_workouts} занятий - это мощно! 💪"
            ])
        elif avg_per_week >= 2:
            facts.extend([
                f"{user_name}, хорошая регулярность! {total_workouts} тренировок за месяц 👍",
                f"Стабильные {total_workouts} тренировок - надежный путь к успеху! 🏃‍♂️"
            ])
        else:
            goal = user.weekly_training_goal or 3
            facts.extend([
                f"{user_name}, попробуйте увеличить частоту до {goal} тренировок в неделю 📈",
                f"Каждая тренировка приближает к цели! Ставьте {goal} занятия в неделю 🎯"
            ])

    elif metric == ProgressMetric.RECOVERY:
        avg_recovery = sum(item.value for item in chart_data) / len(chart_data)

        if avg_recovery >= 80:
            facts.extend([
                f"{user_name}, восстановление на высоте! {avg_recovery:.0f}% - это отлично! 🌟",
                f"Супер! Восстановление {avg_recovery:.0f}% позволяет тренироваться эффективнее! 💫"
            ])
        elif avg_recovery >= 60:
            facts.extend([
                f"{user_name}, нормальное восстановление {avg_recovery:.0f}% 🛌",
                f"Хороший уровень {avg_recovery:.0f}%! Можно добавить интенсивности 📊"
            ])
        else:
            facts.extend([
                f"{user_name}, восстановление {avg_recovery:.0f}% - уделите внимание отдыху 🥗",
                f"Качественный сон улучшит восстановление с {avg_recovery:.0f}%! 💤"
            ])

    elif metric == ProgressMetric.BODY_FAT:
        if trend < -1:
            facts.extend([
                f"{user_name}, отлично! Процент жира снизился на {abs(trend):.1f}% 📉",
                f"Заметный прогресс! Минус {abs(trend):.1f}% жира за месяц 🎯"
            ])
        elif trend > 1:
            facts.extend([
                f"{user_name}, обратите внимание: +{trend:.1f}% жира за месяц 📊",
                f"Рост процента жира на {trend:.1f}% - скорректируйте питание 🥗"
            ])
        else:
            current_fat = chart_data[-1].value if chart_data else 0
            facts.extend([
                f"{user_name}, процент жира стабилен на {current_fat:.1f}% ⚖️",
                f"Стабильный {current_fat:.1f}% жира - хорошая основа для прогресса 📈"
            ])

    # Персонализированные общие факты
    general_facts = [
        f"{user_name}, каждый день прогресса - шаг к лучшей версии себя! 🌈",
        f"Анализ данных помогает достигать целей эффективнее, {user_name}! 📊",
        f"{user_name}, ваше упорство впечатляет! Продолжайте в том же духе! 🚀",
        f"{user_name}, помните: прогресс - это марафон, а не спринт! 🏃‍♂️"
    ]

    return random.choice(facts) if facts else random.choice(general_facts)

async def get_goal_progress(db: AsyncSession, user_id: int, user: User) -> GoalProgress:
    """Получить прогресс по цели пользователя"""
    try:
        # Расчет прогресса цели
        initial_weight = user.initial_weight or user.weight
        current_weight = user.weight
        target_weight = user.target_weight

        weight_lost = 0
        completion_percentage = 0
        daily_calorie_deficit = user.daily_calorie_deficit or 500

        if initial_weight and target_weight:
            weight_lost = initial_weight - current_weight
            total_goal = initial_weight - target_weight
            if total_goal > 0:
                completion_percentage = min(100, max(0, (weight_lost / total_goal) * 100))

        # Расчет стрика недель
        streak_weeks = await calculate_streak_weeks(db, user_id)

        return GoalProgress(
            completion_percentage=round(completion_percentage, 1),
            weight_lost=round(weight_lost, 1),
            daily_calorie_deficit=daily_calorie_deficit,
            streak_weeks=streak_weeks,
            target_weight=target_weight or (current_weight - 5),
            current_weight=current_weight
        )

    except Exception as e:
        logger.error(f"Ошибка в get_goal_progress: {e}")
        return GoalProgress(
            completion_percentage=25.0,
            weight_lost=-2.5,
            daily_calorie_deficit=500,
            streak_weeks=3,
            target_weight=70.0,
            current_weight=75.0
        )


async def calculate_streak_weeks(db: AsyncSession, user_id: int) -> int:
    """Рассчитать стрик недель с тренировками"""
    try:
        # Ищем завершенные тренировки, сгруппированные по неделям
        workouts_result = await db.execute(
            select(Workout)
            .where(and_(
                Workout.user_id == user_id,
                Workout.completed == True
            ))
            .order_by(Workout.scheduled_at.desc())
        )
        workouts = workouts_result.scalars().all()

        if not workouts:
            return 0

        # Группируем по неделям и проверяем последовательность
        current_week = datetime.utcnow().isocalendar()[1]
        streak = 0

        for week in range(current_week, current_week - 10, -1):  # проверяем 10 недель назад
            week_workouts = [w for w in workouts if w.scheduled_at.isocalendar()[1] == week]
            if week_workouts:
                streak += 1
            else:
                break

        return streak

    except Exception as e:
        logger.error(f"Ошибка в calculate_streak_weeks: {e}")
        return random.randint(1, 5)


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
                fat_percentage=30
            )

        # Используем NutritionCalculator
        user_calories = NutritionCalculator.get_user_calorie_needs(user)
        user_goal = getattr(user, 'fitness_goal', 'weight_loss')
        macros = NutritionCalculator.calculate_macros(user_calories, user_goal)

        # Расчет процентов для прогресс-баров
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
            fat_percentage=round(fat_percentage, 1)
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
            fat_percentage=30
        )


@router.get("", response_model=ProgressResponse)
async def get_progress(
        metric: ProgressMetric = ProgressMetric.WEIGHT,
        db: AsyncSession = Depends(get_db)
):
    try:
        # Получаем первого пользователя (для демо)
        user_result = await db.execute(select(User).order_by(User.id).limit(1))
        user = user_result.scalar_one_or_none()

        if not user:
            return await get_demo_progress(metric)

        user_id = user.id

        # Получить данные для графика
        chart_data = await get_progress_chart_data(db, user_id, metric)

        # Получить AI факт на основе графика
        ai_fact = await generate_progress_fact(chart_data, metric, user)

        # Получить прогресс по цели
        goal_progress = await get_goal_progress(db, user_id, user)

        # Получить план питания
        nutrition_plan = await get_nutrition_plan(db, user_id)

        return ProgressResponse(
            selected_metric=metric.value,
            chart_data=chart_data,
            ai_fact=ai_fact,
            goal_progress=goal_progress,
            nutrition_plan=nutrition_plan
        )

    except Exception as e:
        logger.error(f"Ошибка при загрузке прогресса: {str(e)}")
        return await get_demo_progress(metric)


async def get_demo_progress(metric: ProgressMetric) -> ProgressResponse:
    """Демо-данные для разработки"""
    chart_data = await generate_demo_chart_data(metric)

    return ProgressResponse(
        selected_metric=metric.value,
        chart_data=chart_data,
        ai_fact="Демо-режим: это пример AI анализа вашего прогресса! 📊",
        goal_progress=GoalProgress(
            completion_percentage=45.0,
            weight_lost=-3.6,
            daily_calorie_deficit=500,
            streak_weeks=4,
            target_weight=70.0,
            current_weight=76.4
        ),
        nutrition_plan=NutritionPlan(
            calories=1850,
            protein=140,
            carbs=185,
            fat=62,
            protein_percentage=30.3,
            carbs_percentage=40.0,
            fat_percentage=29.7
        )
    )