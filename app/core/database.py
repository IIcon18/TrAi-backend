from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.core.base import Base

# Импортируем ВСЕ модели напрямую
from app.models.user import User
from app.models.goal import Goal, UserGoal
from app.models.workout import Workout, Exercise
from app.models.meal import Meal, Dish
from app.models.progress import Progress
from app.models.post_workout_test import PostWorkoutTest
from app.models.ai_recommendation import AIRecommendation

DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
print("ASYNC DATABASE_URL =", DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)


async def init_database():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        # Удаляем все таблицы если RESET_DATABASE=true
        if settings.RESET_DATABASE:
            print("🧹 RESET_DATABASE=true - пересоздаем БД")
            await conn.run_sync(Base.metadata.drop_all)

        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Таблицы БД созданы/проверены")


async def get_db():
    """Зависимость для получения сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()