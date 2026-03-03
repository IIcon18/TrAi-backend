from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, or_, asc, desc
from datetime import datetime, timedelta
from typing import List, Optional
import math

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.models.user import RoleEnum
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
    ExerciseWithTips,
    WorkoutUpdate,
    WorkoutListItem,
    WorkoutListResponse,
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


@router.get("/ai-usage")
async def get_ai_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию об использовании AI-генераций тренировок."""
    AI_WORKOUT_MONTHLY_LIMIT = 3

    if current_user.role != RoleEnum.user:
        return {"uses": 0, "limit": 0, "unlimited": True}

    now = datetime.utcnow()
    # Сбросить счётчик если прошёл месяц
    if current_user.ai_workout_reset_date is None or \
            (now.year > current_user.ai_workout_reset_date.year or
             now.month > current_user.ai_workout_reset_date.month):
        current_user.ai_workout_uses = 0
        current_user.ai_workout_reset_date = now
        await db.commit()
        await db.refresh(current_user)

    return {
        "uses": current_user.ai_workout_uses,
        "limit": AI_WORKOUT_MONTHLY_LIMIT,
        "unlimited": False,
        "remaining": AI_WORKOUT_MONTHLY_LIMIT - current_user.ai_workout_uses
    }


@router.post("/generate-ai")
async def generate_ai_workout(
    request: AIWorkoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Проверка лимита AI-генераций для бесплатных пользователей (3 в месяц)
    AI_WORKOUT_MONTHLY_LIMIT = 3

    if current_user.role == RoleEnum.user:
        now = datetime.utcnow()
        # Сбросить счётчик если прошёл месяц
        if current_user.ai_workout_reset_date is None or \
                (now.year > current_user.ai_workout_reset_date.year or
                 now.month > current_user.ai_workout_reset_date.month):
            current_user.ai_workout_uses = 0
            current_user.ai_workout_reset_date = now
            await db.commit()
            await db.refresh(current_user)

        if current_user.ai_workout_uses >= AI_WORKOUT_MONTHLY_LIMIT:
            raise HTTPException(
                status_code=403,
                detail=f"Лимит AI-генераций исчерпан ({AI_WORKOUT_MONTHLY_LIMIT}/мес). Перейдите на Pro для безлимитного доступа."
            )

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

    # Инкрементировать счётчик AI-генераций для бесплатных пользователей
    if current_user.role == RoleEnum.user:
        current_user.ai_workout_uses += 1
        if current_user.ai_workout_reset_date is None:
            current_user.ai_workout_reset_date = datetime.utcnow()

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

    # Валидация difficulty
    difficulty = request.get("difficulty", "medium")
    if difficulty not in {"easy", "medium", "hard"}:
        raise HTTPException(status_code=400, detail=f"Invalid difficulty: {difficulty}")

    # Создаем тренировку
    workout = Workout(
        user_id=current_user.id,
        name=request.get("name", "Custom Workout"),
        muscle_group=muscle_group,
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=False,
        difficulty=difficulty,
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


# ==========================
# СПИСОК И ФИЛЬТРАЦИЯ (Lab 3)
# ==========================

@router.get("/list", response_model=WorkoutListResponse)
async def list_workouts(
    search: Optional[str] = Query(None, description="Search by workout name"),
    muscle_group: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    completed: Optional[bool] = Query(None),
    ai_generated: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    sort_by: str = Query("scheduled_at", pattern="^(scheduled_at|name|difficulty)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated, filtered, sorted list of workouts."""
    query = select(Workout).where(Workout.user_id == current_user.id)

    if search:
        query = query.where(Workout.name.ilike(f"%{search}%"))
    if muscle_group:
        query = query.where(Workout.muscle_group == muscle_group)
    if difficulty:
        query = query.where(Workout.difficulty == difficulty)
    if completed is not None:
        query = query.where(Workout.completed == completed)
    if ai_generated is not None:
        query = query.where(Workout.ai_generated == ai_generated)
    if date_from:
        query = query.where(Workout.scheduled_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(Workout.scheduled_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    # Sorting
    sort_col = getattr(Workout, sort_by)
    order_fn = asc if sort_order == "asc" else desc
    query = query.order_by(order_fn(sort_col))

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    workouts = result.scalars().all()

    return WorkoutListResponse(
        items=[WorkoutListItem.model_validate(w) for w in workouts],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.put("/{workout_id}")
async def update_workout(
    workout_id: int,
    data: WorkoutUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit a workout (owner or admin only)."""
    result = await db.execute(select(Workout).where(Workout.id == workout_id))
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    if data.name is not None:
        workout.name = data.name
    if data.muscle_group is not None:
        workout.muscle_group = data.muscle_group
    if data.difficulty is not None:
        workout.difficulty = data.difficulty
    if data.scheduled_at is not None:
        workout.scheduled_at = data.scheduled_at

    await db.commit()
    await db.refresh(workout)
    return {"id": workout.id, "name": workout.name, "muscle_group": workout.muscle_group,
            "difficulty": workout.difficulty, "scheduled_at": workout.scheduled_at.isoformat()}


@router.delete("/{workout_id}", status_code=204)
async def delete_workout(
    workout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a workout (owner or admin only)."""
    result = await db.execute(select(Workout).where(Workout.id == workout_id))
    workout = result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.user_id != current_user.id and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    await db.delete(workout)
    await db.commit()