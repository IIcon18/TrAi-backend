from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, RoleEnum
from app.services.auth_service import auth_service
from datetime import datetime


async def create_test_data(session: AsyncSession):
    test_user = User(
        nickname="TestUser",
        email="test@example.com",
        password=auth_service.hash_password("test123"),
        role=RoleEnum.user,
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

    print(f"Test user created: test@example.com / test123 (role: user)")

    return test_user


async def create_admin_user(session: AsyncSession):
    admin_user = User(
        nickname="Admin",
        email="admin@trai.com",
        password=auth_service.hash_password("admin123"),
        role=RoleEnum.admin,
        profile_completed=True,
        age=30,
        gender="male",
        lifestyle="high",
        height=180,
        weight=80.0,
        initial_weight=80.0,
        target_weight=80.0,
        level="professional",
        weekly_training_goal=5,
        created_at=datetime.utcnow()
    )

    session.add(admin_user)
    await session.commit()
    await session.refresh(admin_user)

    print(f"Admin user created: admin@trai.com / admin123 (role: admin)")

    return admin_user