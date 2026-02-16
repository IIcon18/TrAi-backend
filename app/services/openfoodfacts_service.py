"""
Сервис для работы с OpenFoodFacts API
Документация: https://openfoodfacts.github.io/openfoodfacts-server/api/
"""
import httpx
from typing import List, Dict, Optional


class OpenFoodFactsService:
    BASE_URL = "https://world.openfoodfacts.org/cgi/search.pl"

    def __init__(self):
        self.session = None
        print("🌍 OpenFoodFacts Service initialized")

    async def _get_client(self) -> httpx.AsyncClient:
        """Получить HTTP клиент"""
        if self.session is None:
            self.session = httpx.AsyncClient(
                timeout=30.0,  # Увеличили timeout до 30 секунд
                follow_redirects=True
            )
        return self.session

    def _normalize_nutriments(self, product: Dict) -> Optional[Dict[str, float]]:
        """
        Извлечь БЖУ из продукта OpenFoodFacts.
        Приоритет: данные на 100г
        """
        nutriments = product.get('nutriments', {})

        # Проверяем наличие основных данных
        required_fields = ['energy-kcal_100g', 'proteins_100g', 'fat_100g', 'carbohydrates_100g']

        # Если хотя бы калории есть - берем
        if 'energy-kcal_100g' not in nutriments and 'energy_100g' not in nutriments:
            return None

        # Извлекаем данные (на 100г)
        calories = nutriments.get('energy-kcal_100g') or nutriments.get('energy_100g', 0)
        protein = nutriments.get('proteins_100g', 0)
        fat = nutriments.get('fat_100g', 0)
        carbs = nutriments.get('carbohydrates_100g', 0)

        # Если ккал из кДж
        if calories > 1000:  # скорее всего это кДж
            calories = calories * 0.239  # конвертируем в ккал

        return {
            'calories_per_100g': round(float(calories), 1),
            'protein_per_100g': round(float(protein), 1),
            'fat_per_100g': round(float(fat), 1),
            'carbs_per_100g': round(float(carbs), 1)
        }

    async def search_products(
        self,
        query: str,
        language: str = "ru",
        limit: int = 20
    ) -> List[Dict[str, any]]:
        """
        Поиск продуктов в OpenFoodFacts

        Args:
            query: поисковый запрос (например "яйцо куриное")
            language: язык поиска (ru, en)
            limit: максимум результатов

        Returns:
            Список продуктов с БЖУ
        """
        try:
            print(f"🔍 OpenFoodFacts: Searching for '{query}' (lang: {language})")

            client = await self._get_client()

            # Параметры запроса
            params = {
                'search_terms': query,
                'search_simple': 1,
                'action': 'process',
                'json': 1,
                'page_size': limit,
                'fields': 'product_name,product_name_ru,brands,nutriments,code,image_url,categories'
            }

            response = await client.get(self.BASE_URL, params=params)

            if response.status_code != 200:
                print(f"❌ OpenFoodFacts error: {response.status_code}")
                return []

            data = response.json()
            products = data.get('products', [])

            print(f"✅ OpenFoodFacts: Found {len(products)} products")

            # Обрабатываем результаты
            results = []
            for product in products:
                # Получаем название (приоритет: русское → обычное)
                name = product.get('product_name_ru') or product.get('product_name', '')
                if not name:
                    continue

                # Бренд (если есть)
                brand = product.get('brands', '')
                if brand:
                    name = f"{name} ({brand})"

                # Извлекаем БЖУ
                nutrition = self._normalize_nutriments(product)
                if not nutrition:
                    continue  # Пропускаем продукты без данных

                results.append({
                    'name': name,
                    'code': product.get('code', ''),  # штрихкод
                    'image_url': product.get('image_url', ''),
                    'categories': product.get('categories', ''),
                    'source': 'openfoodfacts',
                    **nutrition
                })

            print(f"📊 OpenFoodFacts: Processed {len(results)} valid products")
            return results

        except httpx.TimeoutException:
            print("⏱️ OpenFoodFacts timeout")
            return []
        except Exception as e:
            print(f"❌ OpenFoodFacts error: {e}")
            return []

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict]:
        """
        Получить продукт по штрихкоду

        Args:
            barcode: штрихкод продукта (например "3017620422003")

        Returns:
            Данные продукта или None
        """
        try:
            print(f"🔍 OpenFoodFacts: Getting product by barcode {barcode}")

            client = await self._get_client()
            url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"

            response = await client.get(url)

            if response.status_code != 200:
                return None

            data = response.json()

            if data.get('status') != 1:
                return None

            product = data.get('product', {})
            name = product.get('product_name_ru') or product.get('product_name', '')

            if not name:
                return None

            nutrition = self._normalize_nutriments(product)
            if not nutrition:
                return None

            return {
                'name': name,
                'code': barcode,
                'image_url': product.get('image_url', ''),
                'source': 'openfoodfacts',
                **nutrition
            }

        except Exception as e:
            print(f"❌ OpenFoodFacts barcode error: {e}")
            return None

    async def close(self):
        """Закрыть HTTP клиент"""
        if self.session:
            await self.session.aclose()
            self.session = None


# Singleton instance
openfoodfacts_service = OpenFoodFactsService()
