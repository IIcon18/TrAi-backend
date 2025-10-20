from fastapi import FastAPI
from app.api.router import api_router
from app.core.db import engine, Base
from sqlalchemy import text
import asyncio

# Явные импорты каждой модели
from app.models.user import User
from app.models.goal import Goal, UserGoal
from app.models.workout import Workout
from app.models.meal import Meal
from app.models.progress import Progress
from app.models.workout_test import WorkoutTest

app = FastAPI(title="TrAi - your personal training intelligence")

app.include_router(api_router)


async def init_database():
    """Асинхронная инициализация БД"""
    print("🔄 Создание таблиц БД...")

    # Проверяем зарегистрированные таблицы
    print(f"📋 Зарегистрированные таблицы: {list(Base.metadata.tables.keys())}")

    if not Base.metadata.tables:
        print("❌ НЕТ ЗАРЕГИСТРИРОВАННЫХ ТАБЛИЦ!")
        return

    async with engine.begin() as conn:
        # Проверяем таблицы ДО создания через run_sync
        def check_tables_sync(conn_sync):
            from sqlalchemy import inspect
            inspector = inspect(conn_sync)
            existing_tables = inspector.get_table_names()
            print(f"📊 Существующие таблицы ДО создания: {existing_tables}")
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

        # Проверяем подключение
        result = await conn.execute(text("SELECT 1"))
        print("✅ База данных успешно подключена")


@app.on_event("startup")
async def startup_event():
    """Асинхронный запуск приложения"""
    await init_database()
    print("🚀 Приложение запущено!")


@app.get("/")
async def root():
    return {"message": "Добро пожаловать в TrAi!"}