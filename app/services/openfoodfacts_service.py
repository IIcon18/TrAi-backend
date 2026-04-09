import asyncio
import hashlib
import json
import time
from typing import Dict, List, Optional

import httpx
import redis.asyncio as aioredis

from app.core.config import settings


class OpenFoodFactsService:
    # --- Конфигурация ---
    TIMEOUT = 8.0
    CACHE_TTL = 3600
    MAX_RETRIES = 2
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60

    @property
    def _search_url(self) -> str:
        return f"{settings.OPENFOODFACTS_BASE_URL}/cgi/search.pl"

    def __init__(self):
        self._http: httpx.AsyncClient | None = None
        self._redis: aioredis.Redis | None = None
        # circuit breaker state
        self._failures: int = 0
        self._open_until: float = 0.0
        print("🌍 OpenFoodFacts Service initialized (production mode)")

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
            )
        return self._http

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._redis


    def _circuit_is_open(self) -> bool:
        """True — сервис временно отключён, не делаем запросы."""
        if self._failures >= self.FAILURE_THRESHOLD:
            if time.monotonic() < self._open_until:
                return True
            # Время восстановления истекло — пробуем снова
            self._failures = 0
        return False

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.FAILURE_THRESHOLD:
            self._open_until = time.monotonic() + self.RECOVERY_TIMEOUT
            print(f"⚡ OpenFoodFacts circuit OPEN — пауза {self.RECOVERY_TIMEOUT}с")

    def _record_success(self) -> None:
        if self._failures > 0:
            print("✅ OpenFoodFacts circuit CLOSED — сервис восстановлен")
        self._failures = 0

    def _cache_key(self, query: str, language: str) -> str:
        digest = hashlib.md5(f"{query.lower().strip()}:{language}".encode()).hexdigest()
        return f"off:search:{digest}"

    async def _cache_get(self, key: str) -> Optional[List]:
        try:
            redis = await self._get_redis()
            raw = await redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass  # Redis недоступен — продолжаем без кеша
        return None

    async def _cache_set(self, key: str, data: List) -> None:
        try:
            redis = await self._get_redis()
            await redis.setex(key, self.CACHE_TTL, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass  # Redis недоступен — просто не кешируем

    def _normalize_nutriments(self, product: Dict) -> Optional[Dict[str, float]]:
        """Извлечь БЖУ из продукта. Приоритет: данные на 100г."""
        nutriments = product.get("nutriments", {})

        if "energy-kcal_100g" not in nutriments and "energy_100g" not in nutriments:
            return None

        calories = nutriments.get("energy-kcal_100g") or nutriments.get(
            "energy_100g", 0
        )
        protein = nutriments.get("proteins_100g", 0)
        fat = nutriments.get("fat_100g", 0)
        carbs = nutriments.get("carbohydrates_100g", 0)

        # Конвертация кДж → ккал
        if calories > 1000:
            calories = calories * 0.239

        return {
            "calories_per_100g": round(float(calories), 1),
            "protein_per_100g": round(float(protein), 1),
            "fat_per_100g": round(float(fat), 1),
            "carbs_per_100g": round(float(carbs), 1),
        }

    def _parse_products(self, data: Dict) -> List[Dict]:
        results = []
        for product in data.get("products", []):
            name = product.get("product_name_ru") or product.get("product_name", "")
            if not name:
                continue
            brand = product.get("brands", "")
            if brand:
                name = f"{name} ({brand})"
            nutrition = self._normalize_nutriments(product)
            if not nutrition:
                continue
            results.append(
                {
                    "name": name,
                    "code": product.get("code", ""),
                    "image_url": product.get("image_url", ""),
                    "categories": product.get("categories", ""),
                    "source": "openfoodfacts",
                    **nutrition,
                }
            )
        return results

    async def search_products(
        self,
        query: str,
        language: str = "ru",
        limit: int = 20,
    ) -> List[Dict]:

        # Circuit breaker — быстрый ответ без ожидания
        if self._circuit_is_open():
            print("⚡ OpenFoodFacts circuit open — пропускаем запрос")
            return []

        # Проверяем кеш
        cache_key = self._cache_key(query, language)
        cached = await self._cache_get(cache_key)
        if cached is not None:
            print(f"📦 OpenFoodFacts cache hit: '{query}'")
            return cached

        print(f"🔍 OpenFoodFacts: поиск '{query}' (lang={language})")

        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": limit,
            "fields": "product_name,product_name_ru,brands,nutriments,code,image_url,categories",
        }

        # Retry с exponential backoff (только при таймауте)
        for attempt in range(self.MAX_RETRIES):
            try:
                client = await self._get_http()
                response = await client.get(self._search_url, params=params)

                if response.status_code != 200:
                    print(f"❌ OpenFoodFacts HTTP {response.status_code}")
                    self._record_failure()
                    return []

                results = self._parse_products(response.json())
                self._record_success()
                print(f"✅ OpenFoodFacts: найдено {len(results)} продуктов")

                await self._cache_set(cache_key, results)
                return results

            except httpx.TimeoutException:
                wait = 2**attempt  # 1с, 2с
                if attempt < self.MAX_RETRIES - 1:
                    print(
                        f"⏱️ OpenFoodFacts timeout (попытка {attempt + 1}), повтор через {wait}с"
                    )
                    await asyncio.sleep(wait)
                else:
                    print("⏱️ OpenFoodFacts timeout — все попытки исчерпаны")
                    self._record_failure()
                    return []

            except Exception as e:
                print(f"❌ OpenFoodFacts error: {e}")
                self._record_failure()
                return []

        return []

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict]:
        """Получить продукт по штрихкоду."""
        if self._circuit_is_open():
            return None

        cache_key = f"off:barcode:{barcode}"
        cached = await self._cache_get(cache_key)
        if cached is not None:
            return cached[0] if cached else None

        try:
            client = await self._get_http()
            url = f"{settings.OPENFOODFACTS_BASE_URL}/api/v0/product/{barcode}.json"
            response = await client.get(url)

            if response.status_code != 200 or response.json().get("status") != 1:
                return None

            product = response.json().get("product", {})
            name = product.get("product_name_ru") or product.get("product_name", "")
            if not name:
                return None

            nutrition = self._normalize_nutriments(product)
            if not nutrition:
                return None

            result = {
                "name": name,
                "code": barcode,
                "image_url": product.get("image_url", ""),
                "source": "openfoodfacts",
                **nutrition,
            }
            self._record_success()
            await self._cache_set(cache_key, [result])
            return result

        except Exception as e:
            print(f"❌ OpenFoodFacts barcode error: {e}")
            self._record_failure()
            return None

    async def close(self) -> None:
        """Закрыть соединения при завершении приложения."""
        if self._http:
            await self._http.aclose()
            self._http = None
        if self._redis:
            await self._redis.aclose()
            self._redis = None

openfoodfacts_service = OpenFoodFactsService()
