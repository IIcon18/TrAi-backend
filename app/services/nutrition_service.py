"""
Сервис для работы с питанием: поиск продуктов, расчет БЖУ, кеширование AI результатов
"""
from typing import Dict, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product, AINutritionCache
from datetime import datetime
import re


class NutritionService:
    @staticmethod
    def _normalize_name(name: str) -> str:
        """Нормализация названия для поиска"""
        # Lowercase и удаление лишних пробелов
        normalized = name.lower().strip()
        # Удаляем спецсимволы
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Множественные пробелы в один
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    @staticmethod
    def _calculate_for_grams(
            calories_per_100g: float,
            protein_per_100g: float,
            fat_per_100g: float,
            carbs_per_100g: float,
            grams: float
    ) -> Dict[str, float]:
        """Пересчет БЖУ на указанное количество грамм"""
        multiplier = grams / 100.0
        return {
            "calories": round(calories_per_100g * multiplier, 1),
            "protein": round(protein_per_100g * multiplier, 1),
            "fat": round(fat_per_100g * multiplier, 1),
            "carbs": round(carbs_per_100g * multiplier, 1)
        }

    async def find_in_database(
            self,
            dish_name: str,
            db: AsyncSession
    ) -> Optional[Product]:
        """Поиск продукта в базе (точное совпадение или вариант)"""
        normalized = self._normalize_name(dish_name)

        # Точное совпадение по name_lower
        result = await db.execute(
            select(Product).where(Product.name_lower == normalized)
        )
        product = result.scalar_one_or_none()
        if product:
            return product

        # Поиск в name_variants
        result = await db.execute(
            select(Product).where(
                Product.name_variants.contains([normalized])
            )
        )
        product = result.scalar_one_or_none()
        if product:
            return product

        # Fuzzy search - проверяем, содержит ли название ключевые слова
        words = normalized.split()
        if len(words) > 1:
            # Ищем по первому значимому слову (не предлогам)
            main_word = next((w for w in words if len(w) > 3), words[0] if words else "")
            if main_word:
                result = await db.execute(
                    select(Product).where(
                        Product.name_lower.like(f"%{main_word}%")
                    ).limit(1)
                )
                product = result.scalar_one_or_none()
                if product:
                    return product

        return None

    async def find_in_cache(
            self,
            dish_name: str,
            db: AsyncSession
    ) -> Optional[AINutritionCache]:
        """Поиск в кеше AI результатов"""
        normalized = self._normalize_name(dish_name)

        result = await db.execute(
            select(AINutritionCache).where(
                AINutritionCache.normalized_name == normalized
            )
        )
        cached = result.scalar_one_or_none()

        if cached:
            # Обновляем счетчик использования и последнее использование
            cached.usage_count += 1
            cached.last_used_at = datetime.utcnow()
            await db.commit()

        return cached

    async def save_to_cache(
            self,
            dish_name: str,
            grams: float,
            nutrition: Dict[str, float],
            source: str,
            db: AsyncSession
    ) -> AINutritionCache:
        """Сохранить результат AI в кеш"""
        normalized = self._normalize_name(dish_name)

        # Рассчитываем значения на 100г
        multiplier = 100.0 / grams
        calories_per_100g = nutrition["calories"] * multiplier
        protein_per_100g = nutrition["protein"] * multiplier
        fat_per_100g = nutrition["fat"] * multiplier
        carbs_per_100g = nutrition["carbs"] * multiplier

        # Проверяем, есть ли уже запись
        result = await db.execute(
            select(AINutritionCache).where(
                AINutritionCache.normalized_name == normalized
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Обновляем существующую запись
            existing.dish_name = dish_name
            existing.grams = grams
            existing.calories = nutrition["calories"]
            existing.protein = nutrition["protein"]
            existing.fat = nutrition["fat"]
            existing.carbs = nutrition["carbs"]
            existing.calories_per_100g = calories_per_100g
            existing.protein_per_100g = protein_per_100g
            existing.fat_per_100g = fat_per_100g
            existing.carbs_per_100g = carbs_per_100g
            existing.source = source
            existing.usage_count += 1
            existing.last_used_at = datetime.utcnow()
            cached = existing
        else:
            # Создаем новую запись
            cached = AINutritionCache(
                dish_name=dish_name,
                normalized_name=normalized,
                grams=grams,
                calories=nutrition["calories"],
                protein=nutrition["protein"],
                fat=nutrition["fat"],
                carbs=nutrition["carbs"],
                calories_per_100g=calories_per_100g,
                protein_per_100g=protein_per_100g,
                fat_per_100g=fat_per_100g,
                carbs_per_100g=carbs_per_100g,
                source=source,
                usage_count=1
            )
            db.add(cached)

        await db.commit()
        await db.refresh(cached)
        return cached

    async def get_nutrition(
            self,
            dish_name: str,
            grams: float,
            db: AsyncSession,
            ai_service=None
    ) -> Dict[str, float]:
        """
        Получить БЖУ для блюда.
        Порядок поиска:
        1. База продуктов
        2. Кеш AI результатов
        3. Вызов AI (если ai_service передан)
        4. Примерные значения (fallback)
        """
        # 1. Ищем в базе продуктов
        product = await self.find_in_database(dish_name, db)
        if product:
            print(f"✅ Найдено в базе: {product.name}")
            return self._calculate_for_grams(
                product.calories_per_100g,
                product.protein_per_100g,
                product.fat_per_100g,
                product.carbs_per_100g,
                grams
            )

        # 2. Ищем в кеше AI
        cached = await self.find_in_cache(dish_name, db)
        if cached:
            print(f"✅ Найдено в кеше AI: {cached.dish_name} (использовано {cached.usage_count} раз)")
            return self._calculate_for_grams(
                cached.calories_per_100g,
                cached.protein_per_100g,
                cached.fat_per_100g,
                cached.carbs_per_100g,
                grams
            )

        # 3. Вызываем AI (если сервис передан)
        if ai_service:
            try:
                print(f"🤖 Запрос к AI для: {dish_name}")
                nutrition = await ai_service.analyze_dish_nutrition(dish_name, grams)

                # Сохраняем результат в кеш
                source = getattr(ai_service, 'last_used_provider', 'unknown')
                await self.save_to_cache(dish_name, grams, nutrition, source, db)

                return nutrition
            except Exception as e:
                print(f"❌ AI не смог проанализировать: {e}")

        # 4. Fallback - примерные значения
        print(f"⚠️ Используем примерные значения для: {dish_name}")
        return self._get_approximate_nutrition(dish_name, grams)

    def _get_approximate_nutrition(self, dish_name: str, grams: float) -> Dict[str, float]:
        """Примерные значения БЖУ на основе категории блюда"""
        normalized = self._normalize_name(dish_name)

        # Категории с примерными значениями на 100г
        categories = {
            "мясо": {"calories": 200, "protein": 20, "fat": 12, "carbs": 0},
            "рыба": {"calories": 150, "protein": 18, "fat": 8, "carbs": 0},
            "овощи": {"calories": 30, "protein": 1, "fat": 0.2, "carbs": 6},
            "фрукты": {"calories": 50, "protein": 0.5, "fat": 0.2, "carbs": 12},
            "крупы": {"calories": 120, "protein": 3, "fat": 1, "carbs": 25},
            "молочное": {"calories": 60, "protein": 3, "fat": 3, "carbs": 5},
            "десерт": {"calories": 300, "protein": 4, "fat": 15, "carbs": 40},
        }

        # Определяем категорию по ключевым словам
        category_keywords = {
            "мясо": ["курица", "говядина", "свинина", "индейка", "мясо"],
            "рыба": ["рыба", "лосось", "тунец", "треска", "семга"],
            "овощи": ["овощи", "салат", "огурец", "помидор", "капуста", "брокколи"],
            "фрукты": ["фрукт", "яблоко", "банан", "апельсин", "груша"],
            "крупы": ["каша", "рис", "гречка", "овсянка", "макароны"],
            "молочное": ["молоко", "творог", "йогурт", "кефир", "сыр"],
            "десерт": ["торт", "пирог", "печенье", "шоколад", "конфеты"],
        }

        detected_category = "крупы"  # дефолт
        for category, keywords in category_keywords.items():
            if any(keyword in normalized for keyword in keywords):
                detected_category = category
                break

        base_nutrition = categories[detected_category]
        return self._calculate_for_grams(
            base_nutrition["calories"],
            base_nutrition["protein"],
            base_nutrition["fat"],
            base_nutrition["carbs"],
            grams
        )


# Singleton instance
nutrition_service = NutritionService()
