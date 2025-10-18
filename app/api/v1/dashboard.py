from fastapi import APIRouter
from typing import List
from app.schemas.dashboard import (
    DashboardResponse,
    ActivityGraph,
    WeeklyProgress,
    AIPlan,
    QuickStats,
    QuickActions,
    BotStatus
)

router = APIRouter()

@router.get("/", response_model=DashboardResponse)
async def get_dashboard():

    activity_graph = [
        ActivityGraph(energy=75, wellbeing=80, timestamp="2025-10-18T12:00:00Z"),
        ActivityGraph(energy=60, wellbeing=70, timestamp="2025-10-19T12:00:00Z")
    ]

    planned_workouts = 5
    completed_workouts = 3

    weekly_progress = WeeklyProgress(
        planned_workouts=planned_workouts,
        completed_workouts=completed_workouts,
        percentage=(completed_workouts / planned_workouts) * 100
    )

    ai_plan = AIPlan(
        calories=2000,
        protein=150.0,
        fat=70.0,
        carbs=250.0
    )

    exercises = [
        {"weight": 50, "reps": 10},
        {"weight": 60, "reps": 8},
        {"weight": 55, "reps": 12},
    ]
    total_weight_reps = sum(e["weight"] * e["reps"] for e in exercises)
    total_reps = sum(e["reps"] for e in exercises)
    average_weight = total_weight_reps / total_reps

    # Среднее восстановление по тесту из 8 вопросов
    recovery_answers = [7, 8, 6, 9, 8, 7, 6, 8]
    average_recovery = (sum(recovery_answers) / len(recovery_answers)) * 10  # 0-100%

    # Прогресс цели
    goal_target = 10
    goal_current = 8
    goal_progress = goal_current
    goal_remaining = goal_target - goal_current

    quick_stats = QuickStats(
        weekly_workouts=completed_workouts,
        total_workouts_goal=planned_workouts,
        average_weight=average_weight,
        average_recovery=average_recovery,
        goal_progress=goal_progress,
        goal_remaining=goal_remaining
    )

    quick_actions = QuickActions(
        open_stats="Открыть статистику",
        change_goal="Изменить цель",
        start_workout="Начать тренировку"
    )

    bot_status = BotStatus(
        connected=True,
        status_color="green"
    )

    return DashboardResponse(
        message="Дашборд пользователя",
        activity_graph=activity_graph,
        weekly_progress=weekly_progress,
        ai_plan=ai_plan,
        quick_stats=quick_stats,
        quick_actions=quick_actions,
        bot_status=bot_status
    )