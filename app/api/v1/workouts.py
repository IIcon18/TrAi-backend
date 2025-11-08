from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime, timedelta
from typing import List

from app.core.db import get_db
from app.schemas.workout import (
    WorkoutCreate, WorkoutResponse, AIWorkoutRequest,
    CompleteWorkoutRequest, WorkoutPageResponse, CalendarEvent,
    QuickAction, ExerciseCompletion
)
from app.models.workout import Workout, Exercise
from app.models.post_workout_test import PostWorkoutTest

router = APIRouter(prefix="/workouts", tags=["workouts"])


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
        )
    ]


async def get_calendar_events(db: AsyncSession, user_id: int) -> List[CalendarEvent]:
    start_date = datetime.utcnow().date()
    calendar_events = []

    for i in range(7):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.isoformat()

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
    tomorrow = (datetime.utcnow() + timedelta(days=1)).date().isoformat()

    for event in calendar_events:
        if event.date == tomorrow:
            if event.type == "workout":
                return f"Завтра тренировка: {event.title}"
            else:
                return "Завтра у вас выходной"

    return "Завтра у вас выходной"


@router.get("/page", response_model=WorkoutPageResponse)
async def get_workout_page(db: AsyncSession = Depends(get_db)):
    user_id = 1

    today = datetime.utcnow().date()
    workout_result = await db.execute(
        select(Workout).where(
            Workout.user_id == user_id,
            func.date(Workout.scheduled_at) == today,
            Workout.completed == False
        )
    )
    active_workout = workout_result.scalar_one_or_none()

    if not active_workout:
        active_workout = await generate_demo_workout(db, user_id)

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

    calendar_events = await get_calendar_events(db, user_id)
    reminder = get_reminder(calendar_events)

    return WorkoutPageResponse(
        workout=workout_response,
        quick_actions=get_quick_actions(),
        calendar=calendar_events,
        reminder=reminder
    )


async def generate_demo_workout(db: AsyncSession, user_id: int) -> Workout:
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
        db: AsyncSession = Depends(get_db)
):
    user_id = 1

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

    # ИСПРАВЛЕНИЕ: убрать .value
    template = workout_templates.get(ai_request.muscle_group)
    if not template:
        raise HTTPException(status_code=400, detail="Неизвестная группа мышц")

    # Удаляем старые тренировки
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
        db: AsyncSession = Depends(get_db)
):
    user_id = 1

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


@router.post("/{workout_id}/complete", response_model=WorkoutResponse)
async def complete_workout(
        workout_id: int,
        complete_data: CompleteWorkoutRequest,
        db: AsyncSession = Depends(get_db)
):
    user_id = 1

    workout_result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == user_id
        )
    )
    workout = workout_result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")

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

    workout.completed = True
    workout.total_weight_lifted = total_weight

    await db.commit()

    exercises_result = await db.execute(
        select(Exercise).where(Exercise.workout_id == workout_id)
    )
    exercises = exercises_result.scalars().all()

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
        } for ex in exercises]
    )


@router.post("/{workout_id}/post-workout-test")
async def create_post_workout_test(
        workout_id: int,
        test_data: dict,
        db: AsyncSession = Depends(get_db)
):
    user_id = 1

    workout_result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == user_id
        )
    )
    workout = workout_result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")

    post_test = PostWorkoutTest(
        user_id=user_id,
        workout_id=workout_id,
        tiredness=test_data.get("tiredness", 5),
        mood=test_data.get("mood", 5),
        energy_level=test_data.get("energy_level", 5),
        avg_rest_time=test_data.get("avg_rest_time", 60),
        completed_exercises=test_data.get("completed_exercises", True),
        pain_discomfort=test_data.get("pain_discomfort", 0),
        performance=test_data.get("performance", 5),
        weight_per_set=test_data.get("weight_per_set", 0),
        recovery_score=test_data.get("recovery_score", 0)
    )

    db.add(post_test)
    await db.commit()
    await db.refresh(post_test)

    return {"message": "Послетренировочный тест сохранен", "test_id": post_test.id}


@router.get("/statistics")
async def get_workout_statistics(db: AsyncSession = Depends(get_db)):
    user_id = 1

    total_workouts_result = await db.execute(
        select(func.count(Workout.id)).where(Workout.user_id == user_id)
    )
    total_workouts = total_workouts_result.scalar()

    completed_workouts_result = await db.execute(
        select(func.count(Workout.id)).where(
            Workout.user_id == user_id,
            Workout.completed == True
        )
    )
    completed_workouts = completed_workouts_result.scalar()

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