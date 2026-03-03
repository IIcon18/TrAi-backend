"""
Скрипт для загрузки начальных продуктов в базу данных
"""
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.product import Product
from app.core.initial_products import INITIAL_PRODUCTS
import asyncio


async def seed_products():
    """Загрузить начальные продукты в базу"""
    async with AsyncSessionLocal() as db:
        # Проверяем, есть ли уже продукты
        result = await db.execute(select(Product))
        existing_products = result.scalars().all()

        if len(existing_products) > 0:
            print(f"База уже содержит {len(existing_products)} продуктов. Пропускаем загрузку.")
            return

        print(f"Загружаем {len(INITIAL_PRODUCTS)} начальных продуктов...")

        for product_data in INITIAL_PRODUCTS:
            product = Product(
                name=product_data["name"],
                name_lower=product_data["name"].lower(),
                name_variants=product_data.get("name_variants", []),
                calories_per_100g=product_data["calories_per_100g"],
                protein_per_100g=product_data["protein_per_100g"],
                fat_per_100g=product_data["fat_per_100g"],
                carbs_per_100g=product_data["carbs_per_100g"],
                category=product_data.get("category"),
                verified=product_data.get("verified", False),
                source="manual"
            )
            db.add(product)

        await db.commit()
        print(f"✅ Успешно загружено {len(INITIAL_PRODUCTS)} продуктов!")


if __name__ == "__main__":
    asyncio.run(seed_products())
