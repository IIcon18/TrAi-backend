from app.models.user import User
from app.models.goal import Goal, UserGoal
from app.models.workout import Workout, Exercise
from app.models.meal import Meal, Dish
from app.models.progress import Progress
from app.models.post_workout_test import PostWorkoutTest
from app.models.ai_recommendation import AIRecommendation

__all__ = [
    "User", "Goal", "UserGoal",
    "Workout", "Exercise",
    "Meal", "Dish",
    "Progress",
    "PostWorkoutTest",
    "AIRecommendation"
]