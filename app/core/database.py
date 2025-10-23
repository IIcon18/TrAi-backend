from app.core.db import engine, Base
from app.core.config import settings
from sqlalchemy import text

from app.models import (
    User, Goal, UserGoal, Workout, Exercise,
    Meal, Dish, Progress, PostWorkoutTest, AIRecommendation
)


async def init_database():
    print("🔄 Инициализация БД...")

    async with engine.begin() as conn:
        #проверяем флаг по бд
        if settings.RESET_DATABASE:
            print("🧹 RESET_DATABASE=true - пересоздаем БД")
            await conn.run_sync(Base.metadata.drop_all)
            print("✅ Старые таблицы удалены")

        #Проверка созданных таблицы
        print(f"Созданные таблицы: {list(Base.metadata.tables.keys())}")

        if not Base.metadata.tables:
            print("Созданных таблиц нету!")
            return

        #проверяем таблицы
        def check_tables_sync(conn_sync):
            from sqlalchemy import inspect
            inspector = inspect(conn_sync)
            existing_tables = inspector.get_table_names()
            print(f"Существующие таблицы ДО создания: {existing_tables}")
            return existing_tables

        existing_tables = await conn.run_sync(check_tables_sync)

        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Таблицы БД созданы/проверены")

        # Проверяем таблицы ПОСЛЕ создания
        def check_tables_after_sync(conn_sync):
            from sqlalchemy import inspect
            inspector = inspect(conn_sync)
            new_tables = inspector.get_table_names()
            print(f"📊 Существующие таблицы ПОСЛЕ создания: {new_tables}")
            return new_tables

        new_tables = await conn.run_sync(check_tables_after_sync)

        #Подключение
        result = await conn.execute(text("SELECT 1"))
        print("✅ База данных успешно подключена")