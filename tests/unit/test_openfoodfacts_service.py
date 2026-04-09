"""
Unit tests для OpenFoodFactsService.

Покрываемые области:
- _normalize_nutriments: стандартные поля, конвертация кДж→ккал, отсутствие данных
- Circuit breaker: открытие после порога, сброс после таймаута, сброс при успехе
- _parse_products: пропуск без имени, пропуск без БЖУ, валидный продукт, приоритет RU-имени
- search_products (async): circuit open → [], cache hit → [], HTTP 500 → failure, успех → сброс failures
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.openfoodfacts_service import OpenFoodFactsService

pytestmark = pytest.mark.unit


@pytest.fixture
def service():
    """Свежий экземпляр сервиса для каждого теста."""
    return OpenFoodFactsService()


# ---------------------------------------------------------------------------
# _normalize_nutriments
# ---------------------------------------------------------------------------

class TestNormalizeNutriments:

    def test_standard_kcal_fields(self, service):
        """Стандартный продукт с energy-kcal_100g — данные возвращаются без изменений."""
        product = {
            "nutriments": {
                "energy-kcal_100g": 89.0,
                "proteins_100g": 1.1,
                "fat_100g": 0.3,
                "carbohydrates_100g": 22.8,
            }
        }
        result = service._normalize_nutriments(product)
        assert result is not None
        assert result["calories_per_100g"] == 89.0
        assert result["protein_per_100g"] == 1.1
        assert result["fat_per_100g"] == 0.3
        assert result["carbs_per_100g"] == 22.8

    def test_kj_conversion(self, service):
        """energy_100g > 1000 трактуется как кДж и конвертируется в ккал (* 0.239)."""
        product = {
            "nutriments": {
                "energy_100g": 1500.0,
                "proteins_100g": 2.0,
                "fat_100g": 1.0,
                "carbohydrates_100g": 10.0,
            }
        }
        result = service._normalize_nutriments(product)
        assert result is not None
        assert result["calories_per_100g"] == round(1500 * 0.239, 1)

    def test_missing_energy_returns_none(self, service):
        """Продукт без поля энергии возвращает None."""
        product = {
            "nutriments": {
                "proteins_100g": 5.0,
                "fat_100g": 2.0,
            }
        }
        result = service._normalize_nutriments(product)
        assert result is None

    def test_empty_nutriments_returns_none(self, service):
        """Пустой блок nutriments возвращает None."""
        product = {"nutriments": {}}
        result = service._normalize_nutriments(product)
        assert result is None

    def test_fallback_to_energy_100g_when_kcal_missing(self, service):
        """Если energy-kcal_100g отсутствует, но есть energy_100g ≤ 1000 — используется напрямую."""
        product = {
            "nutriments": {
                "energy_100g": 350.0,
                "proteins_100g": 3.0,
                "fat_100g": 1.5,
                "carbohydrates_100g": 50.0,
            }
        }
        result = service._normalize_nutriments(product)
        assert result is not None
        assert result["calories_per_100g"] == 350.0


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:

    def test_circuit_closed_initially(self, service):
        """По умолчанию circuit закрыт — запросы разрешены."""
        assert service._circuit_is_open() is False

    def test_circuit_opens_after_failure_threshold(self, service):
        """После FAILURE_THRESHOLD ошибок подряд circuit открывается."""
        for _ in range(service.FAILURE_THRESHOLD):
            service._record_failure()
        assert service._circuit_is_open() is True

    def test_circuit_stays_open_before_recovery(self, service):
        """Circuit остаётся открытым до истечения RECOVERY_TIMEOUT."""
        for _ in range(service.FAILURE_THRESHOLD):
            service._record_failure()
        # Таймаут ещё не истёк
        assert service._open_until > time.monotonic()
        assert service._circuit_is_open() is True

    def test_circuit_resets_after_recovery_timeout(self, service):
        """После истечения RECOVERY_TIMEOUT circuit закрывается и failures сбрасываются."""
        for _ in range(service.FAILURE_THRESHOLD):
            service._record_failure()
        # Симулируем истечение таймаута
        service._open_until = time.monotonic() - 1
        assert service._circuit_is_open() is False
        assert service._failures == 0

    def test_record_success_resets_failure_counter(self, service):
        """_record_success обнуляет счётчик ошибок."""
        service._failures = 3
        service._record_success()
        assert service._failures == 0

    def test_partial_failures_do_not_open_circuit(self, service):
        """Меньше FAILURE_THRESHOLD ошибок — circuit остаётся закрытым."""
        for _ in range(service.FAILURE_THRESHOLD - 1):
            service._record_failure()
        assert service._circuit_is_open() is False


# ---------------------------------------------------------------------------
# _parse_products
# ---------------------------------------------------------------------------

class TestParseProducts:

    def test_skips_product_without_name(self, service):
        """Продукт без имени (product_name и product_name_ru пустые) пропускается."""
        data = {
            "products": [
                {
                    "product_name": "",
                    "product_name_ru": "",
                    "nutriments": {
                        "energy-kcal_100g": 100,
                        "proteins_100g": 1,
                        "fat_100g": 1,
                        "carbohydrates_100g": 10,
                    },
                }
            ]
        }
        result = service._parse_products(data)
        assert result == []

    def test_skips_product_without_nutrition(self, service):
        """Продукт без БЖУ (normalize возвращает None) пропускается."""
        data = {
            "products": [
                {
                    "product_name": "Test Product",
                    "nutriments": {},
                }
            ]
        }
        result = service._parse_products(data)
        assert result == []

    def test_parses_valid_product(self, service):
        """Валидный продукт корректно парсится и добавляется в результат."""
        data = {
            "products": [
                {
                    "product_name": "Banana",
                    "brands": "Chiquita",
                    "nutriments": {
                        "energy-kcal_100g": 89.0,
                        "proteins_100g": 1.1,
                        "fat_100g": 0.3,
                        "carbohydrates_100g": 22.8,
                    },
                    "code": "123456",
                    "image_url": "https://example.com/banana.jpg",
                    "categories": "Fruits",
                }
            ]
        }
        result = service._parse_products(data)
        assert len(result) == 1
        assert result[0]["name"] == "Banana (Chiquita)"
        assert result[0]["source"] == "openfoodfacts"
        assert result[0]["calories_per_100g"] == 89.0
        assert result[0]["code"] == "123456"

    def test_prefers_russian_name_over_english(self, service):
        """product_name_ru имеет приоритет над product_name."""
        data = {
            "products": [
                {
                    "product_name": "Banana",
                    "product_name_ru": "Банан",
                    "nutriments": {
                        "energy-kcal_100g": 89.0,
                        "proteins_100g": 1.1,
                        "fat_100g": 0.3,
                        "carbohydrates_100g": 22.8,
                    },
                }
            ]
        }
        result = service._parse_products(data)
        assert result[0]["name"] == "Банан"

    def test_skips_empty_products_list(self, service):
        """Пустой список products → пустой результат."""
        result = service._parse_products({"products": []})
        assert result == []


# ---------------------------------------------------------------------------
# search_products — async (HTTP и Redis замокированы)
# ---------------------------------------------------------------------------

class TestSearchProducts:

    @pytest.mark.asyncio
    async def test_returns_empty_when_circuit_open(self, service):
        """Если circuit открыт — HTTP-запрос не делается, возвращается []."""
        for _ in range(service.FAILURE_THRESHOLD):
            service._record_failure()

        result = await service.search_products("banana")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_cached_result_without_http(self, service):
        """Cache hit — данные из Redis, HTTP-клиент не вызывается."""
        cached = [{"name": "Банан из кеша", "calories_per_100g": 89.0}]

        with patch.object(service, "_cache_get", new=AsyncMock(return_value=cached)):
            result = await service.search_products("banana")

        assert result == cached

    @pytest.mark.asyncio
    async def test_records_failure_on_http_500(self, service):
        """HTTP 500 от OpenFoodFacts → failure записывается, возвращается []."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(service, "_cache_get", new=AsyncMock(return_value=None)), \
             patch.object(service, "_cache_set", new=AsyncMock()), \
             patch.object(service, "_get_http", new=AsyncMock(return_value=mock_client)):
            result = await service.search_products("banana")

        assert result == []
        assert service._failures == 1

    @pytest.mark.asyncio
    async def test_successful_search_resets_failures(self, service):
        """Успешный запрос обнуляет счётчик ошибок и возвращает продукты."""
        service._failures = 2

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "products": [
                {
                    "product_name": "Banana",
                    "nutriments": {
                        "energy-kcal_100g": 89.0,
                        "proteins_100g": 1.1,
                        "fat_100g": 0.3,
                        "carbohydrates_100g": 22.8,
                    },
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(service, "_cache_get", new=AsyncMock(return_value=None)), \
             patch.object(service, "_cache_set", new=AsyncMock()), \
             patch.object(service, "_get_http", new=AsyncMock(return_value=mock_client)):
            result = await service.search_products("banana")

        assert len(result) == 1
        assert result[0]["name"] == "Banana"
        assert service._failures == 0

    @pytest.mark.asyncio
    async def test_general_exception_records_failure(self, service):
        """Любое исключение при HTTP-запросе → failure, возвращается []."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")

        with patch.object(service, "_cache_get", new=AsyncMock(return_value=None)), \
             patch.object(service, "_cache_set", new=AsyncMock()), \
             patch.object(service, "_get_http", new=AsyncMock(return_value=mock_client)):
            result = await service.search_products("banana")

        assert result == []
        assert service._failures == 1
