from pydantic import BaseModel
from typing import List
from datetime import datetime

class AIRecommendationRead(BaseModel):
    id: int
    type: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True

class EnergyChartData(BaseModel):
    date: str
    energy: int
    mood: int

class WeeklyProgress(BaseModel):
    planned_workouts: int
    completed_workouts: int
    completion_rate: float

class NutritionPlan(BaseModel):
    calories: int
    protein: int
    carbs: int
    fat: int

class CurrentNutrition(BaseModel):
    calories: float
    protein: float
    carbs: float
    fat: float

class QuickStats(BaseModel):
    planned_workouts: int
    total_weight_lifted: float
    recovery_score: float
    goal_progress: float
    weight_change: float

class QuickAction(BaseModel):
    name: str
    icon: str
    route: str

class DashboardResponse(BaseModel):
    user_greeting: str
    progress_fact: str
    last_training_message: str
    weekly_progress_message: str
    energy_chart: List[EnergyChartData]
    weekly_progress: WeeklyProgress
    nutrition_plan: NutritionPlan
    current_nutrition: CurrentNutrition
    quick_stats: QuickStats
    quick_actions: List[QuickAction]
    ai_recommendations: List[AIRecommendationRead]

    class Config:
        from_attributes = True