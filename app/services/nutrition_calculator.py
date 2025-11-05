from typing import Dict
from app.models.user import User


class NutritionCalculator:
    ACTIVITY_MULTIPLIERS = {
        "low": 1.2,
        "medium": 1.55,
        "high": 1.9
    }

    MACRO_RATIOS = {
        "weight_loss": {"protein": 0.35, "carbs": 0.40, "fat": 0.25},
        "maintenance": {"protein": 0.30, "carbs": 0.40, "fat": 0.30},
        "muscle_gain": {"protein": 0.35, "carbs": 0.45, "fat": 0.20}
    }

    @classmethod
    def calculate_bmr(cls, weight: float, height: float, age: int, gender: str) -> float:
        if gender == "female":
            return 10 * weight + 6.25 * height - 5 * age - 161
        else:
            return 10 * weight + 6.25 * height - 5 * age + 5

    @classmethod
    def calculate_tdee(cls, bmr: float, activity_level: str) -> float:
        multiplier = cls.ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
        return bmr * multiplier

    @classmethod
    def calculate_macros(cls, calories: int, goal: str = "maintenance") -> Dict[str, int]:
        ratios = cls.MACRO_RATIOS.get(goal, cls.MACRO_RATIOS["maintenance"])

        protein_g = int((calories * ratios["protein"]) / 4)
        carbs_g = int((calories * ratios["carbs"]) / 4)
        fat_g = int((calories * ratios["fat"]) / 9)

        return {
            "protein": protein_g,
            "carbs": carbs_g,
            "fat": fat_g
        }

    @classmethod
    def get_user_calorie_needs(cls, user: User) -> int:
        if user.ai_calorie_plan and user.ai_calorie_plan > 0:
            return user.ai_calorie_plan

        if all([user.weight, user.height, user.age, user.lifestyle]):
            bmr = cls.calculate_bmr(
                weight=user.weight,
                height=user.height,
                age=user.age,
                gender=user.gender or "male"
            )
            tdee = cls.calculate_tdee(bmr, user.lifestyle)
            return int(tdee)

        return 2000