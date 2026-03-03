"""
Интеграционные тесты эндпоинтов /api/v1/workouts/*.

Покрываемые сценарии:
- Аутентификация: 401/403 для неавторизованных запросов
- GET /workouts/list: возвращает список тренировок
- POST /workouts/create-manual: создание тренировки авторизованным пользователем
- GET /workouts/ai-usage: информация об использовании AI-генераций
- DELETE /workouts/{id}: удаление своей тренировки
- POST /workouts/generate-ai: лимит для user-роли (3/мес), без токена → 403
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from app.models.workout import Workout, Exercise
from app.models.user import RoleEnum

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------

def make_workout(user_id: int, workout_id: int = 1) -> Workout:
    return Workout(
        id=workout_id,
        user_id=user_id,
        name="Тестовая тренировка",
        muscle_group="upper_body_push",
        scheduled_at=datetime.utcnow(),
        completed=False,
        ai_generated=False,
        difficulty="medium",
        total_weight_lifted=0.0,
    )


def make_exercise(workout_id: int) -> Exercise:
    return Exercise(
        id=1,
        workout_id=workout_id,
        name="Отжимания",
        muscle_group="chest",
        sets=3,
        reps=10,
        weight=0.0,
        intensity="low",
        exercise_type="other",
    )


# ---------------------------------------------------------------------------
# GET /workouts/list — список тренировок
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_workouts_list_authenticated_returns_200(user_client, mock_db, user_fixture):
    """Авторизованный пользователь должен получать список тренировок."""
    workout = make_workout(user_fixture.id)

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    workouts_result = MagicMock()
    workouts_result.scalars.return_value.all.return_value = [workout]
    mock_db.execute.side_effect = [count_result, workouts_result]

    response = await user_client.get("/api/v1/workouts/list")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_workouts_list_unauthenticated_returns_403(client, mock_repo):
    """Запрос без токена должен возвращать 403."""
    response = await client.get("/api/v1/workouts/list")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /workouts/create-manual — создание тренировки вручную
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_workout_authenticated_returns_200(user_client, mock_db, user_fixture):
    """Авторизованный пользователь должен успешно создавать тренировку."""
    async def fake_refresh(obj):
        if isinstance(obj, Workout):
            obj.id = 1
            obj.total_weight_lifted = getattr(obj, "total_weight_lifted", None) or 0.0
        elif isinstance(obj, Exercise):
            obj.id = 1

    mock_db.refresh.side_effect = fake_refresh
    mock_db.commit = AsyncMock(return_value=None)
    mock_db.flush = AsyncMock(return_value=None)
    mock_db.add = MagicMock()

    response = await user_client.post("/api/v1/workouts/create-manual", json={
        "name": "Тестовая тренировка",
        "muscle_group": "upper_body_push",
        "exercises": [
            {
                "name": "Отжимания",
                "muscle_group": "chest",
                "sets": 3,
                "reps": 10,
                "weight": 0,
                "intensity": "low",
            }
        ],
    })

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_workout_unauthenticated_returns_403(client, mock_repo):
    """Создание тренировки без токена должно возвращать 403."""
    response = await client.post("/api/v1/workouts/create-manual", json={
        "name": "Test",
        "muscle_group": "upper_body_push",
        "exercises": [],
    })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_workout_invalid_muscle_group_returns_400(user_client, mock_db):
    """Невалидная группа мышц должна возвращать 400 (ручная валидация в endpoint)."""
    response = await user_client.post("/api/v1/workouts/create-manual", json={
        "name": "Test",
        "muscle_group": "invalid_group",
        "exercises": [],
    })
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /workouts/ai-usage — статистика использования AI-генераций
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_ai_usage_as_user_returns_200(user_client, mock_db, user_fixture):
    """Пользователь получает информацию об использовании AI-генераций."""
    # Устанавливаем текущий месяц, чтобы сброс счётчика не срабатывал
    user_fixture.ai_workout_uses = 1
    user_fixture.ai_workout_reset_date = datetime.utcnow()

    response = await user_client.get("/api/v1/workouts/ai-usage")

    assert response.status_code == 200
    data = response.json()
    assert data["unlimited"] is False
    assert data["limit"] == 3


@pytest.mark.asyncio
async def test_get_ai_usage_as_admin_returns_unlimited(admin_client):
    """Администратор имеет неограниченный доступ к AI-генерациям."""
    response = await admin_client.get("/api/v1/workouts/ai-usage")

    assert response.status_code == 200
    data = response.json()
    assert data["unlimited"] is True


# ---------------------------------------------------------------------------
# DELETE /workouts/{workout_id} — удаление тренировки
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_workout_own_success(user_client, mock_db, user_fixture):
    """Пользователь должен успешно удалять свою тренировку."""
    workout = make_workout(user_fixture.id)
    result = MagicMock()
    result.scalar_one_or_none.return_value = workout
    mock_db.execute.return_value = result
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    response = await user_client.delete(f"/api/v1/workouts/{workout.id}")

    assert response.status_code in (200, 204)


@pytest.mark.asyncio
async def test_delete_workout_unauthenticated_returns_403(client, mock_repo):
    """Удаление тренировки без токена должно возвращать 403."""
    response = await client.delete("/api/v1/workouts/1")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /workouts/generate-ai — AI-генерация (лимит для user-роли)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_generate_workout_limit_reached_returns_403(user_client, mock_db, user_fixture):
    """Пользователь, исчерпавший лимит AI-генераций (3/мес), получает 403."""
    # Устанавливаем исчерпанный лимит в текущем месяце
    user_fixture.ai_workout_uses = 3
    user_fixture.ai_workout_reset_date = datetime.utcnow()

    response = await user_client.post("/api/v1/workouts/generate-ai", json={
        "muscle_group": "upper_body_push"
    })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_generate_workout_unauthenticated_returns_403(client, mock_repo):
    """Запрос AI-генерации без токена должен возвращать 403."""
    response = await client.post("/api/v1/workouts/generate-ai", json={
        "muscle_group": "upper_body_push"
    })
    assert response.status_code == 403
