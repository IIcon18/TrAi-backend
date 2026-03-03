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
from app.models.product import Product, AINutritionCache
from app.models.attachment import Attachment

DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

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
            await conn.run_sync(Base.metadata.drop_all)

        await conn.run_sync(Base.metadata.create_all)

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

                -- Add description column to exercises if not exists
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='exercises' AND column_name='description'
                ) THEN
                    ALTER TABLE exercises ADD COLUMN description VARCHAR;
                END IF;

                -- Add equipment column to exercises if not exists
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='exercises' AND column_name='equipment'
                ) THEN
                    ALTER TABLE exercises ADD COLUMN equipment VARCHAR;
                END IF;

                -- RBAC: Add role enum type and column
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'roleenum') THEN
                    CREATE TYPE roleenum AS ENUM ('user', 'pro', 'admin');
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='role'
                ) THEN
                    ALTER TABLE users ADD COLUMN role roleenum DEFAULT 'user' NOT NULL;
                END IF;

                -- RBAC: Add AI workout usage tracking
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='ai_workout_uses'
                ) THEN
                    ALTER TABLE users ADD COLUMN ai_workout_uses INTEGER DEFAULT 0 NOT NULL;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='ai_workout_reset_date'
                ) THEN
                    ALTER TABLE users ADD COLUMN ai_workout_reset_date TIMESTAMP;
                END IF;

                -- Lab 3: Create attachments table if not exists
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name='attachments'
                ) THEN
                    CREATE TABLE attachments (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        entity_type VARCHAR(50) NOT NULL,
                        entity_id INTEGER NOT NULL,
                        filename VARCHAR(255) NOT NULL,
                        s3_key VARCHAR(512) NOT NULL UNIQUE,
                        content_type VARCHAR(100) NOT NULL,
                        size INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                    CREATE INDEX idx_attachments_user_id ON attachments(user_id);
                    CREATE INDEX idx_attachments_entity ON attachments(entity_type, entity_id);
                END IF;
            END $$;
            """)
        )


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()