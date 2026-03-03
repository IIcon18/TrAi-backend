"""
Модульные тесты для NutritionCalculator.

Покрываемые методы:
- calculate_bmr: формула Миффлина–Сан Жеора для мужчин и женщин
- calculate_tdee: умножение BMR на коэффициент активности
- calculate_macros: расчёт БЖУ по целям
- get_user_calorie_needs: приоритет ai_calorie_plan, fallback 2000

Расчёт не зависит от БД или внешних сервисов.
"""

import pytest
from app.services.nutrition_calculator import NutritionCalculator

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# calculate_bmr
# ---------------------------------------------------------------------------

def test_calculate_bmr_male():
    """BMR для мужчины: 10*70 + 6.25*175 - 5*30 + 5 = 1698.75"""
    bmr = NutritionCalculator.calculate_bmr(weight=70, height=175, age=30, gender="male")
    expected = 10 * 70 + 6.25 * 175 - 5 * 30 + 5
    assert bmr == pytest.approx(expected, rel=1e-3)


def test_calculate_bmr_female():
    """BMR для женщины: 10*60 + 6.25*165 - 5*25 - 161 = 1401.25"""
    bmr = NutritionCalculator.calculate_bmr(weight=60, height=165, age=25, gender="female")
    expected = 10 * 60 + 6.25 * 165 - 5 * 25 - 161
    assert bmr == pytest.approx(expected, rel=1e-3)


def test_calculate_bmr_uses_defaults_for_none_values():
    """При передаче None значений должны использоваться дефолты (weight=70, height=170, age=30)."""
    bmr = NutritionCalculator.calculate_bmr(weight=None, height=None, age=None, gender="male")  # type: ignore
    expected = 10 * 70 + 6.25 * 170 - 5 * 30 + 5
    assert bmr == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# calculate_tdee
# ---------------------------------------------------------------------------

def test_calculate_tdee_low_activity():
    """TDEE при низкой активности: BMR * 1.2"""
    bmr = 1600.0
    tdee = NutritionCalculator.calculate_tdee(bmr, "low")
    assert tdee == pytest.approx(bmr * 1.2, rel=1e-3)


def test_calculate_tdee_medium_activity():
    """TDEE при средней активности: BMR * 1.55"""
    bmr = 1600.0
    tdee = NutritionCalculator.calculate_tdee(bmr, "medium")
    assert tdee == pytest.approx(bmr * 1.55, rel=1e-3)


def test_calculate_tdee_high_activity():
    """TDEE при высокой активности: BMR * 1.9"""
    bmr = 1600.0
    tdee = NutritionCalculator.calculate_tdee(bmr, "high")
    assert tdee == pytest.approx(bmr * 1.9, rel=1e-3)


def test_calculate_tdee_unknown_activity_uses_medium_fallback():
    """При неизвестном уровне активности применяется fallback 1.55."""
    bmr = 2000.0
    tdee = NutritionCalculator.calculate_tdee(bmr, "unknown_level")
    assert tdee == pytest.approx(bmr * 1.55, rel=1e-3)


# ---------------------------------------------------------------------------
# calculate_macros
# ---------------------------------------------------------------------------

def test_calculate_macros_maintenance_returns_three_keys():
    """calculate_macros должен вернуть словарь с ключами protein, carbs, fat."""
    macros = NutritionCalculator.calculate_macros(2000, goal="maintenance")
    assert set(macros.keys()) == {"protein", "carbs", "fat"}


def test_calculate_macros_weight_loss_protein_higher():
    """Для цели weight_loss доля белка (0.35) должна быть выше жира (0.25)."""
    macros = NutritionCalculator.calculate_macros(2000, goal="weight_loss")
    assert macros["protein"] > macros["fat"]


def test_calculate_macros_all_values_positive():
    """Все значения макронутриентов должны быть положительными для 2000 ккал."""
    for goal in ("weight_loss", "maintenance", "muscle_gain"):
        macros = NutritionCalculator.calculate_macros(2000, goal=goal)
        assert macros["protein"] > 0
        assert macros["carbs"] > 0
        assert macros["fat"] > 0


def test_calculate_macros_unknown_goal_uses_maintenance():
    """Неизвестная цель должна использовать соотношения для maintenance."""
    macros_maintenance = NutritionCalculator.calculate_macros(2000, goal="maintenance")
    macros_unknown = NutritionCalculator.calculate_macros(2000, goal="unknown_goal")
    assert macros_maintenance == macros_unknown


# ---------------------------------------------------------------------------
# get_user_calorie_needs
# ---------------------------------------------------------------------------

def test_get_user_calorie_needs_uses_ai_plan_if_set():
    """Если ai_calorie_plan > 0, должно возвращаться его значение."""
    from unittest.mock import MagicMock
    user = MagicMock()
    user.ai_calorie_plan = 1800

    result = NutritionCalculator.get_user_calorie_needs(user)
    assert result == 1800


def test_get_user_calorie_needs_calculates_from_profile():
    """При наличии всех данных профиля должен рассчитываться TDEE."""
    from unittest.mock import MagicMock
    from app.models.user import GenderEnum, LifestyleEnum

    user = MagicMock()
    user.ai_calorie_plan = None
    user.weight = 75
    user.height = 180
    user.age = 28
    user.lifestyle = MagicMock(value="medium")
    user.gender = MagicMock(value="male")

    result = NutritionCalculator.get_user_calorie_needs(user)
    assert result > 0
    assert result != 2000  # не дефолтное значение


def test_get_user_calorie_needs_fallback_to_2000():
    """Без данных профиля должна возвращаться дефолтная норма 2000 ккал."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.ai_calorie_plan = None
    user.weight = None
    user.height = None
    user.age = None
    user.lifestyle = None

    result = NutritionCalculator.get_user_calorie_needs(user)
    assert result == 2000
