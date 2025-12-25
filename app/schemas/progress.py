from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class ProgressMetric(str, Enum):
    WEIGHT = "weight"
    BODY_FAT = "body_fat"
    WORKOUTS = "workouts"
    RECOVERY = "recovery"

class ProgressChartData(BaseModel):
    date: str  # "01.11"
    value: float
    label: Optional[str] = None

class GoalProgress(BaseModel):
    completion_percentage: float  # 0-100
    weight_lost: float  # -8 кг
    daily_calorie_deficit: int  # 500 ккал
    streak_weeks: int  # 5 недель
    target_weight: float
    current_weight: float

class NutritionPlan(BaseModel):
    calories: int
    protein: int
    carbs: int
    fat: int
    protein_percentage: float  # для прогресс-баров
    carbs_percentage: float
    fat_percentage: float

class CurrentNutrition(BaseModel):
    calories: float
    protein: float
    carbs: float
    fat: float

class ProgressResponse(BaseModel):
    selected_metric: str
    chart_data: List[ProgressChartData]
    ai_fact: str
    goal_progress: GoalProgress
    nutrition_plan: NutritionPlan
    current_nutrition: CurrentNutrition