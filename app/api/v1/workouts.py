from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime, timedelta
from typing import List

from app.core.db import get_db
from app.core.dependencies import get_current_user  # ← ДОБАВИЛ ЗАЩИТУ
from app.schemas.workout import (
    WorkoutCreate, WorkoutResponse, AIWorkoutRequest,
    CompleteWorkoutRequest, WorkoutPageResponse, CalendarEvent,
    QuickAction, WorkoutCompleteResponse,
    PostWorkoutTestCreate
)
from app.models.workout import Workout, Exercise
from app.models.post_workout_test import PostWorkoutTest
from app.models.user import User  # ← ДОБАВИЛ ДЛЯ ТИПИЗАЦИИ

router = APIRouter(prefix="/workouts", tags=["workouts"])


def get_quick_actions() -> List[QuickAction]:
    """Получить список быстрых действий для страницы тренировок"""
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
        )
    ]


async def get_calendar_events(db: AsyncSession, user_id: int) -> List[CalendarEvent]:
    """Получить события календаря тренировок на 7 дней вперед"""
    start_date = datetime.utcnow().date()
    calendar_events = []

    for i in range(7):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.isoformat()

        # Ищем тренировку на текущую дату
        workout_result = await db.execute(
            select(Workout).where(
                Workout.user_id == user_id,
                func.date(Workout.scheduled_at) == current_date
            )
        )
        workout = workout_result.scalar_one_or_none()

        if workout:
            calendar_events.append(CalendarEvent(
                date=date_str,
                type="workout",
                title=workout.name,
                completed=workout.completed,
                muscle_group=workout.muscle_group
            ))
        else:
            # Если тренировки нет - создаем событие выходного дня
            weekday = current_date.weekday()
            weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

            calendar_events.append(CalendarEvent(
                date=date_str,
                type="rest",
                title=f"Выходной - {weekdays[weekday]}",
                completed=False
            ))

    return calendar_events


def get_reminder(calendar_events: List[CalendarEvent]) -> str:
    """Сгенерировать напоминание о завтрашнем дне"""
    tomorrow = (datetime.utcnow() + timedelta(days=1)).date().isoformat()

    for event in calendar_events:
        if event.date == tomorrow:
            if event.type == "workout":
                return f"Завтра тренировка: {event.title}"
            else:
                return "Завтра у вас выходной"

    return "Завтра у вас выходной"


@router.get("/page", response_model=WorkoutPageResponse)
async def get_workout_page(
    current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
    db: AsyncSession = Depends(get_db)
):
    """Получить главную страницу тренировок с активной тренировкой и календарем"""
    # ИСПОЛЬЗУЕМ current_user.id вместо жесткого user_id - ДОБАВИЛ ЗАЩИТУ
    user_id = current_user.id

    # Ищем активную тренировку на сегодня
    today = datetime.utcnow().date()
    workout_result = await db.execute(
        select(Workout).where(
            Workout.user_id == user_id,
            func.date(Workout.scheduled_at) == today,
            Workout.completed == False
        )
    )
    active_workout = workout_result.scalar_one_or_none()

    # Если активной тренировки нет - генерируем демо
    if not active_workout:
        active_workout = await generate_demo_workout(db, user_id)

    # Формируем ответ с упражнениями
    workout_response = None
    if active_workout:
        exercises_result = await db.execute(
            select(Exercise).where(Exercise.workout_id == active_workout.id)
        )
        exercises = exercises_result.scalars().all()

        workout_response = WorkoutResponse(
            id=active_workout.id,
            name=active_workout.name,
            muscle_group=active_workout.muscle_group,
            scheduled_at=active_workout.scheduled_at,
            completed=active_workout.completed,
            total_weight_lifted=active_workout.total_weight_lifted,
            ai_generated=active_workout.ai_generated,
            exercises=[{
                "id": ex.id,
                "name": ex.name,
                "muscle_group": ex.muscle_group,
                "sets": ex.sets,
                "reps": ex.reps,
                "weight": ex.weight,
                "intensity": ex.intensity
            } for ex in exercises]
        )

    # Получаем календарь и напоминания
    calendar_events = await get_calendar_events(db, user_id)
    reminder = get_reminder(calendar_events)

    return WorkoutPageResponse(
        workout=workout_response,
        quick_actions=get_quick_actions(),
        calendar=calendar_events,
        reminder=reminder
    )


async def generate_demo_workout(db: AsyncSession, user_id: int) -> Workout:
    """Сгенерировать демо-тренировку когда нет активных тренировок"""
    workout_templates = {
        "upper_body_push": {
            "name": "Upper Body Push Workout",
            "exercises": [
                {"name": "Bench Press", "muscle_group": "chest", "sets": 4, "reps": 8, "weight": 0,
                 "intensity": "medium"},
                {"name": "Shoulder Press", "muscle_group": "shoulders", "sets": 3, "reps": 10, "weight": 0,
                 "intensity": "medium"},
                {"name": "Tricep Extensions", "muscle_group": "triceps", "sets": 3, "reps": 12, "weight": 0,
                 "intensity": "low"}
            ]
        }
    }

    template = workout_templates["upper_body_push"]

    # Создаем тренировку
    workout = Workout(
        user_id=user_id,
        name=template["name"],
        muscle_group="upper_body_push",
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=True
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    # Добавляем упражнения
    for ex_data in template["exercises"]:
        exercise = Exercise(
            workout_id=workout.id,
            name=ex_data["name"],
            muscle_group=ex_data["muscle_group"],
            sets=ex_data["sets"],
            reps=ex_data["reps"],
            weight=ex_data["weight"],
            intensity=ex_data["intensity"],
            exercise_type="other"
        )
        db.add(exercise)

    await db.commit()
    return workout


@router.post("/generate-ai", response_model=WorkoutResponse)
async def generate_ai_workout(
        ai_request: AIWorkoutRequest,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Сгенерировать AI тренировку по выбранной группе мышц"""
    # ИСПОЛЬЗУЕМ current_user.id вместо жесткого user_id - ДОБАВИЛ ЗАЩИТУ
    user_id = current_user.id

    workout_templates = {
        "upper_body_push": {
            "name": "Upper Body Push Workout",
            "exercises": [
                {"name": "Bench Press", "muscle_group": "chest", "sets": 4, "reps": 8, "weight": 0,
                 "intensity": "medium"},
                {"name": "Shoulder Press", "muscle_group": "shoulders", "sets": 3, "reps": 10, "weight": 0,
                 "intensity": "medium"},
                {"name": "Tricep Extensions", "muscle_group": "triceps", "sets": 3, "reps": 12, "weight": 0,
                 "intensity": "low"}
            ]
        },
        "upper_body_pull": {
            "name": "Upper Body Pull Workout",
            "exercises": [
                {"name": "Pull-ups", "muscle_group": "back", "sets": 4, "reps": 8, "weight": 0, "intensity": "high"},
                {"name": "Bent Over Rows", "muscle_group": "back", "sets": 3, "reps": 10, "weight": 0,
                 "intensity": "medium"},
                {"name": "Bicep Curls", "muscle_group": "biceps", "sets": 3, "reps": 12, "weight": 0,
                 "intensity": "low"}
            ]
        },
        "lower_body": {
            "name": "Lower Body Workout",
            "exercises": [
                {"name": "Squats", "muscle_group": "legs", "sets": 4, "reps": 8, "weight": 0, "intensity": "high"},
                {"name": "Deadlifts", "muscle_group": "legs", "sets": 3, "reps": 6, "weight": 0, "intensity": "high"},
                {"name": "Lunges", "muscle_group": "legs", "sets": 3, "reps": 10, "weight": 0, "intensity": "medium"}
            ]
        },
        "core_stability": {
            "name": "Core & Stability Workout",
            "exercises": [
                {"name": "Plank", "muscle_group": "core", "sets": 3, "reps": 60, "weight": 0, "intensity": "medium"},
                {"name": "Russian Twists", "muscle_group": "core", "sets": 3, "reps": 15, "weight": 0,
                 "intensity": "medium"},
                {"name": "Leg Raises", "muscle_group": "core", "sets": 3, "reps": 12, "weight": 0, "intensity": "low"}
            ]
        }
    }

    template = workout_templates.get(ai_request.muscle_group)
    if not template:
        raise HTTPException(status_code=400, detail="Неизвестная группа мышц")

    # Удаляем незавершенные тренировки на сегодня
    today = datetime.utcnow().date()
    workouts_result = await db.execute(
        select(Workout).where(
            Workout.user_id == user_id,
            func.date(Workout.scheduled_at) == today,
            Workout.completed == False
        )
    )
    workouts_to_delete = workouts_result.scalars().all()

    for workout in workouts_to_delete:
        await db.execute(
            delete(Exercise).where(Exercise.workout_id == workout.id)
        )
        await db.execute(
            delete(Workout).where(Workout.id == workout.id)
        )

    await db.commit()

    # Создаем новую AI тренировку
    workout = Workout(
        user_id=user_id,
        name=template["name"],
        muscle_group=ai_request.muscle_group,
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=True
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    # Добавляем упражнения из шаблона
    exercises_data = []
    for ex_data in template["exercises"]:
        exercise = Exercise(
            workout_id=workout.id,
            name=ex_data["name"],
            muscle_group=ex_data["muscle_group"],
            sets=ex_data["sets"],
            reps=ex_data["reps"],
            weight=ex_data["weight"],
            intensity=ex_data["intensity"],
            exercise_type="other"
        )
        db.add(exercise)
        exercises_data.append(exercise)

    await db.commit()

    return WorkoutResponse(
        id=workout.id,
        name=workout.name,
        muscle_group=workout.muscle_group,
        scheduled_at=workout.scheduled_at,
        completed=workout.completed,
        total_weight_lifted=workout.total_weight_lifted,
        ai_generated=workout.ai_generated,
        exercises=[{
            "id": ex.id,
            "name": ex.name,
            "muscle_group": ex.muscle_group,
            "sets": ex.sets,
            "reps": ex.reps,
            "weight": ex.weight,
            "intensity": ex.intensity
        } for ex in exercises_data]
    )


@router.post("/custom", response_model=WorkoutResponse)
async def create_custom_workout(
        workout_data: WorkoutCreate,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Создать пользовательскую тренировку"""
    # ИСПОЛЬЗУЕМ current_user.id вместо жесткого user_id - ДОБАВИЛ ЗАЩИТУ
    user_id = current_user.id

    # Удаляем незавершенные тренировки на сегодня
    today = datetime.utcnow().date()
    workouts_result = await db.execute(
        select(Workout).where(
            Workout.user_id == user_id,
            func.date(Workout.scheduled_at) == today,
            Workout.completed == False
        )
    )
    workouts_to_delete = workouts_result.scalars().all()

    for workout in workouts_to_delete:
        await db.execute(
            delete(Exercise).where(Exercise.workout_id == workout.id)
        )
        await db.execute(
            delete(Workout).where(Workout.id == workout.id)
        )

    await db.commit()

    # Создаем новую тренировку
    workout = Workout(
        user_id=user_id,
        name=workout_data.name,
        muscle_group=workout_data.muscle_group.value,
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=False
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    # Добавляем упражнения из запроса
    exercises_data = []
    for ex_data in workout_data.exercises:
        exercise = Exercise(
            workout_id=workout.id,
            name=ex_data.name,
            muscle_group=ex_data.muscle_group,
            sets=ex_data.sets,
            reps=ex_data.reps,
            weight=ex_data.weight,
            intensity=ex_data.intensity.value,
            exercise_type="other"
        )
        db.add(exercise)
        exercises_data.append(exercise)

    await db.commit()

    return WorkoutResponse(
        id=workout.id,
        name=workout.name,
        muscle_group=workout.muscle_group,
        scheduled_at=workout.scheduled_at,
        completed=workout.completed,
        total_weight_lifted=workout.total_weight_lifted,
        ai_generated=workout.ai_generated,
        exercises=[{
            "id": ex.id,
            "name": ex.name,
            "muscle_group": ex.muscle_group,
            "sets": ex.sets,
            "reps": ex.reps,
            "weight": ex.weight,
            "intensity": ex.intensity
        } for ex in exercises_data]
    )


@router.post("/{workout_id}/complete", response_model=WorkoutCompleteResponse)
async def complete_workout(
        workout_id: int,
        complete_data: CompleteWorkoutRequest,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Завершить тренировку и обновить данные упражнений"""
    # ИСПОЛЬЗУЕМ current_user.id вместо жесткого user_id - ДОБАВИЛ ЗАЩИТУ
    user_id = current_user.id

    # Находим тренировку
    workout_result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == user_id
        )
    )
    workout = workout_result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")

    # Обновляем вес и параметры упражнений
    total_weight = 0
    for ex_data in complete_data.exercises:
        exercise_result = await db.execute(
            select(Exercise).where(Exercise.id == ex_data.id)
        )
        exercise = exercise_result.scalar_one_or_none()

        if exercise:
            exercise.weight = ex_data.weight
            if ex_data.intensity:
                exercise.intensity = ex_data.intensity
            if ex_data.reps:
                exercise.reps = ex_data.reps
            total_weight += ex_data.weight * exercise.sets

    # Помечаем тренировку завершенной
    workout.completed = True
    workout.total_weight_lifted = total_weight

    await db.commit()

    # Получаем обновленные упражнения
    exercises_result = await db.execute(
        select(Exercise).where(Exercise.workout_id == workout_id)
    )
    exercises = exercises_result.scalars().all()

    workout_response = WorkoutResponse(
        id=workout.id,
        name=workout.name,
        muscle_group=workout.muscle_group,
        scheduled_at=workout.scheduled_at,
        completed=workout.completed,
        total_weight_lifted=workout.total_weight_lifted,
        ai_generated=workout.ai_generated,
        exercises=[{
            "id": ex.id,
            "name": ex.name,
            "muscle_group": ex.muscle_group,
            "sets": ex.sets,
            "reps": ex.reps,
            "weight": ex.weight,
            "intensity": ex.intensity
        } for ex in exercises]
    )

    return WorkoutCompleteResponse(
        **workout_response.dict(),
        show_post_test=complete_data.take_post_test
    )


@router.post("/{workout_id}/post-workout-test")
async def create_post_workout_test(
        workout_id: int,
        test_data: PostWorkoutTestCreate,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Создать послетренировочный тест"""
    # ИСПОЛЬЗУЕМ current_user.id вместо жесткого user_id - ДОБАВИЛ ЗАЩИТУ
    user_id = current_user.id

    # Проверяем что тренировка существует
    workout_result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == user_id
        )
    )
    workout = workout_result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")

    # Расчет общего результата по 7 вопросам
    positive_score = (test_data.mood + test_data.energy_level + test_data.performance) / 3
    negative_score = (test_data.tiredness + test_data.pain_discomfort) / 2
    rest_time_score = 10 - min(abs(test_data.avg_rest_time - 90) / 15, 5)
    completion_bonus = 2 if test_data.completed_exercises else 0

    overall_score = (
            positive_score * 0.4 +
            (10 - negative_score) * 0.3 +
            rest_time_score * 0.2 +
            completion_bonus * 0.1
    )

    final_score = max(1, min(10, round(overall_score, 1)))

    # Создаем запись теста
    post_test = PostWorkoutTest(
        user_id=user_id,
        workout_id=workout_id,
        tiredness=test_data.tiredness,
        mood=test_data.mood,
        energy_level=test_data.energy_level,
        avg_rest_time=test_data.avg_rest_time,
        completed_exercises=test_data.completed_exercises,
        pain_discomfort=test_data.pain_discomfort,
        performance=test_data.performance,
        weight_per_set=0,
        recovery_score=final_score
    )

    db.add(post_test)
    await db.commit()
    await db.refresh(post_test)

    return {
        "message": "Послетренировочный тест сохранен",
        "test_id": post_test.id,
        "overall_score": final_score,
        "interpretation": get_interpretation(final_score)
    }


def get_interpretation(score: float) -> str:
    """Интерпретировать результат послетренировочного теста"""
    if score >= 9:
        return "Отличная тренировка! 💪"
    elif score >= 7:
        return "Хорошая тренировка! 👍"
    elif score >= 5:
        return "Нормальная тренировка 👌"
    elif score >= 3:
        return "Сложная тренировка 😓"
    else:
        return "Очень тяжелая тренировка 🆘"


@router.get("/statistics")
async def get_workout_statistics(
    current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
    db: AsyncSession = Depends(get_db)
):
    """Получить статистику тренировок пользователя"""
    # ИСПОЛЬЗУЕМ current_user.id вместо жесткого user_id - ДОБАВИЛ ЗАЩИТУ
    user_id = current_user.id

    # Общее количество тренировок
    total_workouts_result = await db.execute(
        select(func.count(Workout.id)).where(Workout.user_id == user_id)
    )
    total_workouts = total_workouts_result.scalar()

    # Завершенные тренировки
    completed_workouts_result = await db.execute(
        select(func.count(Workout.id)).where(
            Workout.user_id == user_id,
            Workout.completed == True
        )
    )
    completed_workouts = completed_workouts_result.scalar()

    # Суммарный поднятый вес
    total_weight_result = await db.execute(
        select(func.coalesce(func.sum(Workout.total_weight_lifted), 0)).where(
            Workout.user_id == user_id,
            Workout.completed == True
        )
    )
    total_weight = total_weight_result.scalar()

    return {
        "total_workouts": total_workouts,
        "completed_workouts": completed_workouts,
        "completion_rate": (completed_workouts / total_workouts * 100) if total_workouts > 0 else 0,
        "total_weight_lifted": total_weight,
        "average_workouts_per_week": completed_workouts / 4
    }