from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.core.base import Base

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
    async with engine.begin() as conn:
        if settings.RESET_DATABASE:
            print("RESET_DATABASE=true - recreating DB")
            await conn.run_sync(Base.metadata.drop_all)

        await conn.run_sync(Base.metadata.create_all)
        print("Tables created/verified")

        # Migration: add new columns if they don't exist and make fields nullable
        await conn.execute(
            text("""
            DO $$
            BEGIN
                -- Add nickname column if not exists
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='nickname'
                ) THEN
                    ALTER TABLE users ADD COLUMN nickname VARCHAR DEFAULT 'User';
                    UPDATE users SET nickname = 'User' WHERE nickname IS NULL;
                    ALTER TABLE users ALTER COLUMN nickname SET NOT NULL;
                END IF;

                -- Add profile_completed column if not exists
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='profile_completed'
                ) THEN
                    ALTER TABLE users ADD COLUMN profile_completed BOOLEAN DEFAULT true;
                END IF;

                -- Make age, height, weight, lifestyle nullable for two-step registration
                ALTER TABLE users ALTER COLUMN age DROP NOT NULL;
                ALTER TABLE users ALTER COLUMN height DROP NOT NULL;
                ALTER TABLE users ALTER COLUMN weight DROP NOT NULL;
                ALTER TABLE users ALTER COLUMN lifestyle DROP NOT NULL;
            END $$;
            """)
        )
        print("Migration completed")


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()