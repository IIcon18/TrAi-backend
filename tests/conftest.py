"""
Общие фикстуры для всех тестов TrAi backend.

Стратегия:
- Тестовое FastAPI-приложение создаётся без startup-событий (нет подключения к БД/MinIO).
- UserRepository заменяется на AsyncMock (mock_repo) во всех тестах auth.
- Для эндпоинтов с прямым доступом к БД (admin, workouts, attachments)
  зависимость get_db заменяется на mock_db, а get_current_user — на лямбду с нужным пользователем.
- JWT-токены создаются через auth_service.create_access_token() для проверки middleware.
"""

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


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def create_test_app() -> FastAPI:
    """Тестовое FastAPI-приложение без startup-событий."""
    test_app = FastAPI(title="TrAi Test App")
    test_app.include_router(api_router, prefix="/api/v1")
    return test_app


def make_auth_headers(user: User) -> dict:
    """Создать заголовки авторизации с валидным JWT для указанного пользователя."""
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    return {"Authorization": f"Bearer {access_token}"}


# ---------------------------------------------------------------------------
# Фикстуры пользователей
# ---------------------------------------------------------------------------

@pytest.fixture
def user_fixture() -> User:
    """Обычный пользователь с ролью 'user'."""
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
    """Администратор с ролью 'admin'."""
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
    """Пользователь с ролью 'pro'."""
    return User(
        id=3,
        email="pro@example.com",
        nickname="prouser",
        password=auth_service.hash_password("pro123"),
        role=RoleEnum.pro,
        profile_completed=True,
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Фикстуры для зависимостей
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_repo() -> AsyncMock:
    """Мокированный UserRepository для auth-эндпоинтов."""
    return AsyncMock(spec=UserRepository)


@pytest.fixture
def mock_db() -> MagicMock:
    """
    Мокированная сессия БД для эндпоинтов, использующих get_db напрямую.
    execute() возвращает MagicMock с предустановленными методами.
    """
    session = AsyncMock()
    default_result = MagicMock()
    default_result.scalar_one_or_none.return_value = None
    default_result.scalar_one.return_value = 0
    default_result.scalars.return_value.all.return_value = []
    session.execute.return_value = default_result
    return session


# ---------------------------------------------------------------------------
# HTTP-клиенты
# ---------------------------------------------------------------------------

@pytest.fixture
async def client(mock_repo) -> AsyncGenerator[AsyncClient, None]:
    """
    Базовый клиент: get_user_repository → mock_repo.
    Используется для auth-эндпоинтов (register, login, refresh, logout, me).
    """
    app = create_test_app()
    app.dependency_overrides[get_user_repository] = lambda: mock_repo
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def user_client(user_fixture, mock_repo, mock_db) -> AsyncGenerator[AsyncClient, None]:
    """
    Клиент, аутентифицированный как обычный пользователь.
    get_current_user → user_fixture, get_db → mock_db.
    """
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
    """
    Клиент, аутентифицированный как администратор.
    get_current_user → admin_fixture, get_db → mock_db.
    """
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
    """Клиент, аутентифицированный как pro-пользователь."""
    app = create_test_app()
    app.dependency_overrides[get_user_repository] = lambda: mock_repo
    app.dependency_overrides[get_current_user] = lambda: pro_fixture
    app.dependency_overrides[get_db] = lambda: mock_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
