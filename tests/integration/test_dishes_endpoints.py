"""
Интеграционные тесты /api/v1/dishes/* endpoints.

Сценарии:
- RBAC: только pro/admin могут искать блюда, создавать meal, анализировать
- POST /dishes/search: результаты из БД, fallback на OpenFoodFacts, fallback на AI
- POST /dishes/search: graceful degradation — все источники недоступны → 200 с []
- POST /dishes/analyze: пустой запрос → 400, успешный анализ → 200
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Вспомогательная функция — мок результата DB с продуктами
# ---------------------------------------------------------------------------

def db_returns_products(mock_db, products: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = products
    mock_db.execute.return_value = result


def db_returns_no_products(mock_db):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = result


def make_mock_product(name: str = "Банан", calories: float = 89.0):
    p = MagicMock()
    p.id = 1
    p.name = name
    p.calories_per_100g = calories
    p.protein_per_100g = 1.1
    p.fat_per_100g = 0.3
    p.carbs_per_100g = 22.8
    return p


# ---------------------------------------------------------------------------
# RBAC — роли
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_blocked_for_user_role(user_client):
    """Обычный пользователь (role=user) не может искать блюда — только pro/admin."""
    response = await user_client.post("/api/v1/dishes/search", json={"query": "банан"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_meal_blocked_for_user_role(user_client):
    """Обычный пользователь не может создавать приём пищи."""
    response = await user_client.post("/api/v1/dishes/create-meal", json={"type": "breakfast"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_analyze_blocked_for_user_role(user_client):
    """Обычный пользователь не может анализировать блюдо через AI."""
    response = await user_client.post(
        "/api/v1/dishes/analyze", json={"query": "банан", "grams": 100}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_search_allowed_for_admin(admin_client, mock_db):
    """Администратор может искать блюда."""
    db_returns_products(mock_db, [make_mock_product()])
    response = await admin_client.post("/api/v1/dishes/search", json={"query": "банан"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /dishes/search — поиск в БД
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_returns_database_results(pro_client, mock_db):
    """Если продукт найден в БД — возвращается без вызова OpenFoodFacts."""
    db_returns_products(mock_db, [make_mock_product("Банан")])

    with patch("app.api.v1.dishes.openfoodfacts_service") as mock_off:
        response = await pro_client.post("/api/v1/dishes/search", json={"query": "банан"})
        mock_off.search_products.assert_not_called()

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "database"
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Банан"


@pytest.mark.asyncio
async def test_search_response_structure(pro_client, mock_db):
    """Ответ содержит обязательные поля: query, results, total_count, source."""
    db_returns_products(mock_db, [make_mock_product()])

    response = await pro_client.post("/api/v1/dishes/search", json={"query": "банан"})

    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "total_count" in data
    assert "source" in data


# ---------------------------------------------------------------------------
# POST /dishes/search — fallback на OpenFoodFacts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_falls_back_to_openfoodfacts_when_db_empty(pro_client, mock_db):
    """Если в БД ничего нет — запрашивает OpenFoodFacts."""
    db_returns_no_products(mock_db)
    mock_db.commit = AsyncMock()

    off_products = [
        {
            "name": "Банан (Chiquita)",
            "calories_per_100g": 89.0,
            "protein_per_100g": 1.1,
            "fat_per_100g": 0.3,
            "carbs_per_100g": 22.8,
            "source": "openfoodfacts",
        }
    ]

    with patch("app.api.v1.dishes.openfoodfacts_service") as mock_off:
        mock_off.search_products = AsyncMock(return_value=off_products)
        response = await pro_client.post("/api/v1/dishes/search", json={"query": "банан"})
        mock_off.search_products.assert_called_once()

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "openfoodfacts"
    assert data["total_count"] >= 1
    assert data["results"][0]["name"] == "Банан (Chiquita)"


@pytest.mark.asyncio
async def test_search_falls_back_to_ai_when_off_returns_empty(pro_client, mock_db):
    """Если OpenFoodFacts вернул [] — запрашивает AI."""
    db_returns_no_products(mock_db)

    ai_nutrition = {"calories": 89, "protein": 1.1, "fat": 0.3, "carbs": 22.8}

    with patch("app.api.v1.dishes.openfoodfacts_service") as mock_off, \
         patch("app.api.v1.dishes.nutrition_service") as mock_nutrition:
        mock_off.search_products = AsyncMock(return_value=[])
        mock_nutrition.get_nutrition = AsyncMock(return_value=ai_nutrition)

        response = await pro_client.post("/api/v1/dishes/search", json={"query": "банан"})

        mock_nutrition.get_nutrition.assert_called_once()

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "ai"
    assert data["total_count"] == 1


# ---------------------------------------------------------------------------
# POST /dishes/search — graceful degradation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_graceful_degradation_all_sources_fail(pro_client, mock_db):
    """Если все источники недоступны — возвращает 200 с пустым списком, не 500."""
    db_returns_no_products(mock_db)

    with patch("app.api.v1.dishes.openfoodfacts_service") as mock_off, \
         patch("app.api.v1.dishes.nutrition_service") as mock_nutrition:
        mock_off.search_products = AsyncMock(return_value=[])
        mock_nutrition.get_nutrition = AsyncMock(side_effect=Exception("AI unavailable"))

        response = await pro_client.post(
            "/api/v1/dishes/search", json={"query": "непонятноечто123"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["total_count"] == 0


@pytest.mark.asyncio
async def test_search_empty_query_returns_popular_products(pro_client, mock_db):
    """Пустой запрос возвращает популярные продукты из БД."""
    db_returns_products(mock_db, [make_mock_product("Куриная грудка", 165)])

    response = await pro_client.post("/api/v1/dishes/search", json={"query": ""})

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "database"


# ---------------------------------------------------------------------------
# POST /dishes/analyze — AI-анализ
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_empty_query_returns_400(pro_client):
    """Пустое (или пробельное) название блюда → 400."""
    response = await pro_client.post(
        "/api/v1/dishes/analyze", json={"query": "   ", "grams": 100}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_returns_nutrition_data(pro_client, mock_db):
    """Успешный AI-анализ возвращает поля dish_name, grams и nutrition."""
    ai_nutrition = {"calories": 89, "protein": 1.1, "fat": 0.3, "carbs": 22.8}

    with patch("app.api.v1.dishes.nutrition_service") as mock_nutrition, \
         patch("app.api.v1.dishes.ai_service") as mock_ai:
        mock_nutrition.get_nutrition = AsyncMock(return_value=ai_nutrition)
        mock_ai.last_used_provider = "openai"

        response = await pro_client.post(
            "/api/v1/dishes/analyze", json={"query": "банан", "grams": 150}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["dish_name"] == "банан"
    assert data["grams"] == 150
    assert "nutrition" in data
    assert data["nutrition"]["calories"] == 89


@pytest.mark.asyncio
async def test_analyze_ai_failure_returns_500(pro_client, mock_db):
    """Если AI недоступен — возвращает 500 с описанием ошибки."""
    with patch("app.api.v1.dishes.nutrition_service") as mock_nutrition:
        mock_nutrition.get_nutrition = AsyncMock(side_effect=Exception("AI timeout"))

        response = await pro_client.post(
            "/api/v1/dishes/analyze", json={"query": "банан", "grams": 100}
        )

    assert response.status_code == 500
    assert "detail" in response.json()
