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
from app.models.progress import Progress

router = APIRouter(tags=["workouts"])


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


async def update_progress_on_workout_completion(
    db: AsyncSession,
    user_id: int,
    workout: Workout
) -> None:
    """
    Update Progress record when a workout is completed.
    Increments completed_workouts count for today.
    """
    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)

        # Find existing Progress record for today
        result = await db.execute(
            select(Progress).where(
                Progress.user_id == user_id,
                Progress.recorded_at >= today_start,
                Progress.recorded_at <= today_end
            )
        )
        progress_record = result.scalar_one_or_none()

        if progress_record:
            # Update existing record
            progress_record.completed_workouts += 1
            if workout.total_weight_lifted:
                progress_record.total_lifted_weight += workout.total_weight_lifted
        else:
            # Create new Progress record for today
            progress_record = Progress(
                user_id=user_id,
                completed_workouts=1,
                total_lifted_weight=workout.total_weight_lifted or 0,
                recorded_at=datetime.utcnow()
            )
            db.add(progress_record)

        await db.commit()

    except Exception as e:
        await db.rollback()


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
        ).limit(1)
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
                "description": e.description or "",
                "equipment": e.equipment or "none",
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

    # Получаем реальную цель пользователя
    user_goal = "general_fitness"
    if current_user.current_goal_id:
        from app.models.goal import Goal
        goal_result = await db.execute(
            select(Goal).where(Goal.id == current_user.current_goal_id)
        )
        goal = goal_result.scalar_one_or_none()
        if goal and goal.type:
            user_goal = goal.type.value

    # Загружаем историю тренировок для разнообразия
    history_result = await db.execute(
        select(Workout)
        .where(
            Workout.user_id == current_user.id,
            Workout.muscle_group == normalized_group
        )
        .order_by(Workout.created_at.desc())
        .limit(5)
    )
    recent_workouts = history_result.scalars().all()

    workout_history = []
    for w in recent_workouts:
        ex_result = await db.execute(
            select(Exercise).where(Exercise.workout_id == w.id)
        )
        exercises = ex_result.scalars().all()
        workout_history.append({
            "name": w.name,
            "muscle_group": w.muscle_group,
            "exercises": [
                {"name": e.name, "muscle_group": e.muscle_group}
                for e in exercises
            ]
        })

    try:
        ai_data = await ai_service.generate_ai_workout(
            user_data={
                "lifestyle": current_user.lifestyle.value if current_user.lifestyle else "low",
                "gender": current_user.gender.value if current_user.gender else "not_specified",
                "age": current_user.age,
                "goal": user_goal,
                "level": current_user.level.value if getattr(current_user, "level", None) else "beginner",
            },
            muscle_group=normalized_group,
            workout_history=workout_history
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

    exercises_list = []
    for ex in ai_data["exercises"]:
        # Используем вес из AI если указан, иначе 0
        weight = ex.get("weight", 0)

        exercise = Exercise(
            workout_id=workout.id,
            name=ex["name"],
            description=ex.get("description", ""),
            equipment=ex.get("equipment", "none"),
            muscle_group=ex["muscle_group"],
            sets=ex["sets"],
            reps=ex["reps"],
            weight=weight,
            intensity=ex["intensity"],
            exercise_type="other"
        )
        db.add(exercise)
        await db.flush()

        exercises_list.append({
            "id": exercise.id,
            "name": exercise.name,
            "description": exercise.description,
            "equipment": exercise.equipment,
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


@router.post("/create-manual")
async def create_manual_workout(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать тренировку вручную (не через AI)
    """
    # Валидация muscle_group
    muscle_group = request.get("muscle_group", "upper_body_push")
    allowed_groups = {"upper_body_push", "upper_body_pull", "core_stability", "lower_body"}
    if muscle_group not in allowed_groups:
        raise HTTPException(status_code=400, detail=f"Invalid muscle_group: {muscle_group}")

    # Создаем тренировку
    workout = Workout(
        user_id=current_user.id,
        name=request.get("name", "Custom Workout"),
        muscle_group=muscle_group,
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=False,
        difficulty="medium"
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    # Добавляем упражнения
    exercises_list = []
    for ex_data in request.get("exercises", []):
        exercise = Exercise(
            workout_id=workout.id,
            name=ex_data.get("name", "Exercise"),
            description=ex_data.get("description", ""),
            equipment=ex_data.get("equipment", "bodyweight"),
            muscle_group=muscle_group,
            sets=ex_data.get("sets", 3),
            reps=ex_data.get("reps", 10),
            weight=ex_data.get("weight", 0),
            intensity=ex_data.get("intensity", "medium"),
            exercise_type="other"
        )
        db.add(exercise)
        await db.flush()

        exercises_list.append({
            "id": exercise.id,
            "name": exercise.name,
            "description": exercise.description,
            "equipment": exercise.equipment,
            "sets": exercise.sets,
            "reps": exercise.reps,
            "weight": exercise.weight,
            "intensity": exercise.intensity
        })

    await db.commit()

    return {
        "id": workout.id,
        "name": workout.name,
        "muscle_group": workout.muscle_group,
        "scheduled_at": workout.scheduled_at.isoformat(),
        "completed": workout.completed,
        "exercises": exercises_list
    }


@router.post("/{workout_id}/complete")
async def complete_workout(
    workout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a workout as completed and update Progress tracking.
    """
    # Get the workout
    result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == current_user.id
        )
    )
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    if workout.completed:
        raise HTTPException(status_code=400, detail="Workout already completed")

    # Calculate total weight lifted from exercises
    exercises_result = await db.execute(
        select(Exercise).where(Exercise.workout_id == workout.id)
    )
    exercises = exercises_result.scalars().all()

    total_weight = sum(ex.sets * ex.reps * ex.weight for ex in exercises)
    workout.total_weight_lifted = total_weight

    # Mark as completed
    workout.completed = True
    await db.commit()

    # Update Progress record
    await update_progress_on_workout_completion(db, current_user.id, workout)

    return {
        "message": "Workout completed successfully",
        "workout_id": workout.id,
        "completed": workout.completed,
        "total_weight_lifted": total_weight
    }