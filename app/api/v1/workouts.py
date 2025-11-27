from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime, timedelta
from typing import List

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.schemas.workout import (
    WorkoutCreate, WorkoutResponse, AIWorkoutRequest,
    CompleteWorkoutRequest, WorkoutPageResponse, CalendarEvent,
    QuickAction, WorkoutCompleteResponse,
    PostWorkoutTestCreate, AIWorkoutAnalysis,
    AIWorkoutResponse, ExerciseWithTips
)
from app.models.workout import Workout, Exercise
from app.models.post_workout_test import PostWorkoutTest
from app.models.user import User
from app.services.ai_service import ai_service

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
async def get_workout_page(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id

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

@router.post("/generate-ai", response_model=AIWorkoutResponse)
async def generate_ai_workout(
        ai_request: AIWorkoutRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id

    workouts_result = await db.execute(
        select(Workout)
        .where(Workout.user_id == user_id)
        .order_by(Workout.scheduled_at.desc())
        .limit(5)
    )
    recent_workouts = workouts_result.scalars().all()

    workout_history = []
    for workout in recent_workouts:
        exercises_result = await db.execute(
            select(Exercise).where(Exercise.workout_id == workout.id)
        )
        exercises = exercises_result.scalars().all()

        workout_history.append({
            "name": workout.name,
            "muscle_group": workout.muscle_group,
            "completed": workout.completed,
            "exercises": [
                {
                    "name": ex.name,
                    "sets": ex.sets,
                    "reps": ex.reps,
                    "weight": ex.weight
                } for ex in exercises
            ]
        })

    user_data = {
        "level": current_user.level.value if current_user.level else "beginner",
        "gender": current_user.gender.value if current_user.gender else "not_specified",
        "age": current_user.age,
        "goal": "general_fitness"
    }

    try:
        ai_workout = await ai_service.generate_ai_workout(
            user_data=user_data,
            muscle_group=ai_request.muscle_group.value,
            workout_history=workout_history
        )
    except Exception as e:
        return await generate_ai_workout_fallback(ai_request, current_user, db)

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
        await db.execute(delete(Exercise).where(Exercise.workout_id == workout.id))
        await db.execute(delete(Workout).where(Workout.id == workout.id))

    await db.commit()

    workout = Workout(
        user_id=user_id,
        name=ai_workout["name"],
        muscle_group=ai_request.muscle_group.value,
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=True,
        difficulty="medium"
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    exercises_data = []
    for ex_data in ai_workout["exercises"]:
        exercise = Exercise(
            workout_id=workout.id,
            name=ex_data["name"],
            muscle_group=ex_data["muscle_group"],
            sets=ex_data["sets"],
            reps=ex_data["reps"],
            weight=0,
            intensity=ex_data["intensity"],
            exercise_type="other"
        )
        db.add(exercise)
        await db.flush()

        exercises_data.append(ExerciseWithTips(
            id=exercise.id,
            name=exercise.name,
            muscle_group=exercise.muscle_group,
            sets=exercise.sets,
            reps=exercise.reps,
            weight=exercise.weight,
            intensity=exercise.intensity,
            tips=ex_data.get("tips", ""),
            weight_suggestion=ex_data.get("weight_suggestion", "")
        ))

    await db.commit()

    return AIWorkoutResponse(
        id=workout.id,
        name=workout.name,
        muscle_group=workout.muscle_group,
        scheduled_at=workout.scheduled_at,
        completed=workout.completed,
        total_weight_lifted=workout.total_weight_lifted,
        ai_generated=workout.ai_generated,
        exercises=exercises_data,
        description=ai_workout.get("description", "")
    )

@router.post("/custom", response_model=WorkoutResponse)
async def create_custom_workout(
        workout_data: WorkoutCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id

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
        await db.execute(delete(Exercise).where(Exercise.workout_id == workout.id))
        await db.execute(delete(Workout).where(Workout.id == workout.id))

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


@router.post("/{workout_id}/complete", response_model=WorkoutCompleteResponse)
async def complete_workout(
        workout_id: int,
        complete_data: CompleteWorkoutRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id

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
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id

    workout_result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == user_id
        )
    )
    workout = workout_result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Тренировка не найдена")

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
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id

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


@router.post("/{workout_id}/analyze", response_model=AIWorkoutAnalysis)
async def analyze_workout(
        workout_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id

    workout_result = await db.execute(
        select(Workout).where(
            Workout.id == workout_id,
            Workout.user_id == user_id,
            Workout.completed == True
        )
    )
    workout = workout_result.scalar_one_or_none()

    if not workout:
        raise HTTPException(status_code=404, detail="Завершенная тренировка не найдена")

    exercises_result = await db.execute(
        select(Exercise).where(Exercise.workout_id == workout_id)
    )
    exercises = exercises_result.scalars().all()

    test_result = await db.execute(
        select(PostWorkoutTest).where(PostWorkoutTest.workout_id == workout_id)
    )
    post_test = test_result.scalar_one_or_none()

    workout_data = {
        "name": workout.name,
        "muscle_group": workout.muscle_group,
        "total_weight": workout.total_weight_lifted,
        "exercises": [
            {
                "name": ex.name,
                "sets": ex.sets,
                "reps": ex.reps,
                "weight": ex.weight,
                "intensity": ex.intensity
            } for ex in exercises
        ]
    }

    user_feedback = {
        "recovery_score": post_test.recovery_score if post_test else None,
        "performance": post_test.performance if post_test else None,
        "energy_level": post_test.energy_level if post_test else None,
        "mood": post_test.mood if post_test else None
    }

    try:
        analysis = await ai_service.analyze_workout_performance(
            workout_data=workout_data,
            user_feedback=user_feedback
        )

        return AIWorkoutAnalysis(
            workout_id=workout_id,
            analysis=analysis,
            success=True
        )

    except Exception as e:
        return AIWorkoutAnalysis(
            workout_id=workout_id,
            analysis="Не удалось проанализировать тренировку",
            success=False
        )