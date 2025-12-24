from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime, timedelta
from typing import List

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.workout import Workout, Exercise
from app.models.post_workout_test import PostWorkoutTest
from app.models.user import User
from app.schemas.workout import (
    WorkoutCreate,
    WorkoutResponse,
    AIWorkoutRequest,
    CompleteWorkoutRequest,
    WorkoutPageResponse,
    CalendarEvent,
    QuickAction,
    WorkoutCompleteResponse,
    PostWorkoutTestCreate,
    AIWorkoutAnalysis,
    AIWorkoutResponse,
    ExerciseWithTips
)
from app.services.ai_service import ai_service

router = APIRouter(prefix="/workouts", tags=["workouts"])


# ==========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================

def get_quick_actions() -> List[QuickAction]:
    return [
        QuickAction(name="Открыть статистику", icon="📊", route="/progress"),
        QuickAction(name="Изменить цель", icon="🎯", route="/goals"),
    ]


async def generate_demo_workout(db: AsyncSession, user_id: int) -> Workout:
    workout = Workout(
        user_id=user_id,
        name="Базовая тренировка",
        muscle_group="full_body",
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=False,
        difficulty="easy"
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    exercises = [
        Exercise(
            workout_id=workout.id,
            name="Приседания",
            muscle_group="legs",
            sets=3,
            reps=12,
            weight=0,
            intensity="low",
            exercise_type="other"
        ),
        Exercise(
            workout_id=workout.id,
            name="Отжимания",
            muscle_group="chest",
            sets=3,
            reps=10,
            weight=0,
            intensity="low",
            exercise_type="other"
        ),
    ]

    db.add_all(exercises)
    await db.commit()

    return workout


async def get_calendar_events(db: AsyncSession, user_id: int) -> List[CalendarEvent]:
    today = datetime.utcnow().date()
    events = []

    for i in range(7):
        day = today + timedelta(days=i)

        result = await db.execute(
            select(Workout).where(
                Workout.user_id == user_id,
                func.date(Workout.scheduled_at) == day
            )
        )
        workout = result.scalar_one_or_none()

        if workout:
            events.append(CalendarEvent(
                date=day.isoformat(),
                type="workout",
                title=workout.name,
                completed=workout.completed,
                muscle_group=workout.muscle_group
            ))
        else:
            events.append(CalendarEvent(
                date=day.isoformat(),
                type="rest",
                title="Выходной",
                completed=False
            ))

    return events


# ==========================
# ENDPOINTS
# ==========================

# ==========================
# ENDPOINTS
# ==========================

@router.get("/page")
async def get_workout_page(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    today = datetime.utcnow().date()

    result = await db.execute(
        select(Workout).where(
            Workout.user_id == current_user.id,
            func.date(Workout.scheduled_at) == today,
            Workout.completed == False
        )
    )
    workout = result.scalar_one_or_none()

    if not workout:
        workout = await generate_demo_workout(db, current_user.id)

    exercises_result = await db.execute(
        select(Exercise).where(Exercise.workout_id == workout.id)
    )
    exercises = exercises_result.scalars().all()

    workout_response = {
        "id": workout.id,
        "name": workout.name,
        "muscle_group": workout.muscle_group,
        "scheduled_at": workout.scheduled_at.isoformat(),
        "completed": workout.completed,
        "exercises": [
            {
                "id": e.id,
                "name": e.name,
                "sets": e.sets,
                "reps": e.reps,
                "weight": e.weight,
                "intensity": e.intensity
            } for e in exercises
        ]
    }

    return {"workout": workout_response}


@router.post("/generate-ai")
async def generate_ai_workout(
    request: AIWorkoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Небольшая ручная валидация/нормализация группы мышц,
    # чтобы поддержать старые значения с фронта и избежать 422 от Pydantic
    raw_group = request.muscle_group
    aliases = {
        "upper_push": "upper_body_push",
        "upper_pull": "upper_body_pull",
        "core": "core_stability",
        "lower": "lower_body",
    }
    normalized_group = aliases.get(raw_group, raw_group)

    allowed_groups = {"upper_body_push", "upper_body_pull", "core_stability", "lower_body"}
    if normalized_group not in allowed_groups:
        raise HTTPException(status_code=400, detail=f"Invalid muscle_group: {raw_group}")

    try:
        ai_data = await ai_service.generate_ai_workout(
            user_data={
                "lifestyle": current_user.lifestyle.value if current_user.lifestyle else "low",
                "gender": current_user.gender.value if current_user.gender else "not_specified",
                "age": current_user.age,
                "goal": "general_fitness",
                "level": current_user.level.value if getattr(current_user, "level", None) else "beginner",
            },
            muscle_group=normalized_group,
            workout_history=[]
        )
    except Exception:
        raise HTTPException(status_code=500, detail="AI не смог сгенерировать тренировку")

    workout = Workout(
        user_id=current_user.id,
        name=ai_data["name"],
        # сохраняем уже нормализованную группу мышц
        muscle_group=normalized_group,
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=True,
        difficulty="medium"
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    BASE_WEIGHTS = {"low": 20, "medium": 40, "high": 60}
    user_lifestyle = current_user.lifestyle.value if current_user.lifestyle else "low"
    base_weight = BASE_WEIGHTS.get(user_lifestyle, 20)

    exercises_list = []
    for ex in ai_data["exercises"]:
        exercise = Exercise(
            workout_id=workout.id,
            name=ex["name"],
            muscle_group=ex["muscle_group"],
            sets=ex["sets"],
            reps=ex["reps"],
            weight=base_weight,
            intensity=ex["intensity"],
            exercise_type="other"
        )
        db.add(exercise)
        await db.flush()

        exercises_list.append({
            "id": exercise.id,
            "name": exercise.name,
            "sets": exercise.sets,
            "reps": exercise.reps,
            "weight": exercise.weight,
            "intensity": exercise.intensity
        })

    await db.commit()

    workout_response = {
        "id": workout.id,
        "name": workout.name,
        "muscle_group": workout.muscle_group,
        "scheduled_at": workout.scheduled_at.isoformat(),
        "completed": workout.completed,
        "exercises": exercises_list
    }

    return workout_response