"""
E2E тесты сценариев работы со сторонним API (OpenFoodFacts) и пагинации.

Задание 4.3: пагинация/фильтрация — GET /admin/users?page=1&page_size=3
Задание 4.5: сторонний API при штатной работе и отказах.

Сценарии:
1. Поиск блюда → не найдено в БД → найдено в OpenFoodFacts → 200
2. OpenFoodFacts недоступен (возвращает []) → AI как fallback → 200
3. Все источники недоступны → 200 с пустым массивом (не 500)
4. Пагинация: GET /admin/users с page и page_size → корректный total и количество записей
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.user import User, RoleEnum
from app.services.auth_service import auth_service

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Сценарий 1: OpenFoodFacts работает штатно — продукт найден
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_search_openfoodfacts_success(pro_client, mock_db):
    """
    E2E (задание 4.5): Поиск → нет в БД → найдено в OpenFoodFacts → 200.
    Проверяем: source=openfoodfacts, корректные поля продукта.
    """
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = db_result
    mock_db.commit = AsyncMock()

    off_products = [
        {
            "name": "Творог 9%",
            "calories_per_100g": 159.0,
            "protein_per_100g": 17.0,
            "fat_per_100g": 9.0,
            "carbs_per_100g": 2.0,
            "source": "openfoodfacts",
        }
    ]

    with patch("app.api.v1.dishes.openfoodfacts_service") as mock_off:
        mock_off.search_products = AsyncMock(return_value=off_products)
        response = await pro_client.post("/api/v1/dishes/search", json={"query": "творог"})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "openfoodfacts"
    assert body["total_count"] == 1
    assert body["results"][0]["name"] == "Творог 9%"
    assert body["results"][0]["calories_per_100g"] == 159.0


# ---------------------------------------------------------------------------
# Сценарий 2: OpenFoodFacts недоступен — circuit breaker вернул [] → AI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_search_openfoodfacts_unavailable_falls_back_to_ai(pro_client, mock_db):
    """
    E2E (задание 4.5): OFF circuit открыт (возвращает []) → AI как резервный источник.
    Проверяем: приложение не падает, возвращает данные из AI.
    """
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = db_result

    ai_nutrition = {"calories": 159, "protein": 17.0, "fat": 9.0, "carbs": 2.0}

    with patch("app.api.v1.dishes.openfoodfacts_service") as mock_off, \
         patch("app.api.v1.dishes.nutrition_service") as mock_nutrition:
        mock_off.search_products = AsyncMock(return_value=[])  # circuit open → []
        mock_nutrition.get_nutrition = AsyncMock(return_value=ai_nutrition)

        response = await pro_client.post("/api/v1/dishes/search", json={"query": "творог"})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ai"
    assert body["total_count"] == 1
    assert body["results"][0]["calories_per_100g"] == 159


# ---------------------------------------------------------------------------
# Сценарий 3: Все источники недоступны → graceful degradation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_all_sources_fail_returns_empty_not_500(pro_client, mock_db):
    """
    E2E (задание 4.5): БД пуста, OFF вернул [], AI выбросил исключение.
    Проверяем: ответ 200 с пустым results, а не 500.
    """
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = db_result

    with patch("app.api.v1.dishes.openfoodfacts_service") as mock_off, \
         patch("app.api.v1.dishes.nutrition_service") as mock_nutrition:
        mock_off.search_products = AsyncMock(return_value=[])
        mock_nutrition.get_nutrition = AsyncMock(side_effect=Exception("Timeout"))

        response = await pro_client.post(
            "/api/v1/dishes/search", json={"query": "абракадабра"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["total_count"] == 0


# ---------------------------------------------------------------------------
# Сценарий 4: Пагинация — GET /admin/users?page=1&page_size=3
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_admin_users_pagination(admin_client, mock_db):
    """
    E2E (задание 4.3): Пагинация GET /admin/users.
    Проверяем: total отражает полное количество, users — только страницу.
    """
    all_users = [
        User(
            id=i,
            email=f"user{i}@test.com",
            nickname=f"user{i}",
            password=auth_service.hash_password("pass"),
            role=RoleEnum.user,
            profile_completed=False,
            created_at=datetime.utcnow(),
        )
        for i in range(1, 6)  # 5 пользователей всего
    ]

    # Первый execute — COUNT запрос
    count_result = MagicMock()
    count_result.scalar_one.return_value = 5

    # Второй execute — список страницы (первые 3)
    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = all_users[:3]

    mock_db.execute.side_effect = [count_result, page_result]

    response = await admin_client.get("/api/v1/admin/users?page=1&page_size=3")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 3
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_e2e_admin_users_second_page(admin_client, mock_db):
    """
    E2E (задание 4.3): Вторая страница содержит оставшихся пользователей.
    """
    all_users = [
        User(
            id=i,
            email=f"user{i}@test.com",
            nickname=f"user{i}",
            password=auth_service.hash_password("pass"),
            role=RoleEnum.user,
            profile_completed=False,
            created_at=datetime.utcnow(),
        )
        for i in range(4, 6)  # пользователи 4 и 5 — вторая страница
    ]

    count_result = MagicMock()
    count_result.scalar_one.return_value = 5

    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = all_users

    mock_db.execute.side_effect = [count_result, page_result]

    response = await admin_client.get("/api/v1/admin/users?page=2&page_size=3")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 2
