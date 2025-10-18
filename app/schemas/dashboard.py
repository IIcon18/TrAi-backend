from pydantic import BaseModel
from typing import List

class ActivityGraph(BaseModel):
    energy: float
    mood: float
    timestamp: str

class WeeklyProgress(BaseModel):
    planned_workouts: int
    completed_workouts: int
    persentage: float

class AIPlan(BaseModel):
    calories: int
    proteins: float
    fat: float
    carbs: float

class QuickStats(BaseModel):
    weekly_workouts: int
    total_workouts_goal: int
    average_weight: float
    average_recovery: float
    goal_progress: float
    goal_remaining: float

class QuickActions(BaseModel):
    open_stats: str
    change_goal: str
    start_workout: str

class BotStatus(BaseModel):
    connected: bool
    status_color: str  # "green" или "red"

class DashboardResponse(BaseModel):
    message: str
    activity_graph: List[ActivityGraph]
    weekly_progress: WeeklyProgress
    ai_plan: AIPlan
    quick_stats: QuickStats
    quick_actions: QuickActions
    bot_status: BotStatus