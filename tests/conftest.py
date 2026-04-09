import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime
from typing import AsyncGenerator

from app.api.router import api_router
from app.models.user import User, RoleEnum
from app.services.auth_service import auth_service
from app.repositories.user_repository import UserRepository
from app.core.dependencies import get_current_user, get_user_repository
from app.core.db import get_db

def create_test_app() -> FastAPI:
    test_app = FastAPI(title="TrAi Test App")
    test_app.include_router(api_router, prefix="/api/v1")
    return test_app


def make_auth_headers(user: User) -> dict:
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture
def user_fixture() -> User:
    return User(
        id=1,
        email="test@example.com",
        nickname="tester",
        password=auth_service.hash_password("password123"),
        role=RoleEnum.user,
        profile_completed=False,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def admin_fixture() -> User:
    return User(
        id=2,
        email="admin@example.com",
        nickname="admin",
        password=auth_service.hash_password("admin123"),
        role=RoleEnum.admin,
        profile_completed=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def pro_fixture() -> User:
    return User(
        id=3,
        email="pro@example.com",
        nickname="prouser",
        password=auth_service.hash_password("pro123"),
        role=RoleEnum.pro,
        profile_completed=True,
        created_at=datetime.utcnow(),
    )

@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock(spec=UserRepository)


@pytest.fixture
def mock_db() -> MagicMock:
    session = AsyncMock()
    default_result = MagicMock()
    default_result.scalar_one_or_none.return_value = None
    default_result.scalar_one.return_value = 0
    default_result.scalars.return_value.all.return_value = []
    session.execute.return_value = default_result
    return session

@pytest.fixture
async def client(mock_repo) -> AsyncGenerator[AsyncClient, None]:
    app = create_test_app()
    app.dependency_overrides[get_user_repository] = lambda: mock_repo
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def user_client(user_fixture, mock_repo, mock_db) -> AsyncGenerator[AsyncClient, None]:
    app = create_test_app()
    app.dependency_overrides[get_user_repository] = lambda: mock_repo
    app.dependency_overrides[get_current_user] = lambda: user_fixture
    app.dependency_overrides[get_db] = lambda: mock_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def admin_client(admin_fixture, mock_repo, mock_db) -> AsyncGenerator[AsyncClient, None]:
    app = create_test_app()
    app.dependency_overrides[get_user_repository] = lambda: mock_repo
    app.dependency_overrides[get_current_user] = lambda: admin_fixture
    app.dependency_overrides[get_db] = lambda: mock_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def pro_client(pro_fixture, mock_repo, mock_db) -> AsyncGenerator[AsyncClient, None]:
    app = create_test_app()
    app.dependency_overrides[get_user_repository] = lambda: mock_repo
    app.dependency_overrides[get_current_user] = lambda: pro_fixture
    app.dependency_overrides[get_db] = lambda: mock_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
