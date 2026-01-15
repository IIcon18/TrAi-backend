from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from datetime import datetime


async def create_test_data(session: AsyncSession):
    test_user = User(
        nickname="TestUser",
        email="test@example.com",
        password="hashed_password",
        age=25,
        gender="male",
        lifestyle="medium",
        height=180,
        weight=75.0,
        initial_weight=80.0,
        target_weight=70.0,
        weekly_training_goal=3,
        level="beginner",
        created_at=datetime.utcnow()
    )


    session.add(test_user)
    await session.commit()
    await session.refresh(test_user)

    print(f"✅ Создан тестовый пользователь: {test_user.email} (ID: {test_user.id})")

    return test_user