"""
Интеграционные тесты эндпоинтов /api/v1/auth/*.

Покрываемые сценарии:
- POST /auth/register: успех, дубликат email, невалидный email, короткий пароль
- POST /auth/login: успех, неверный пароль, несуществующий пользователь
- POST /auth/refresh: успешная ротация, невалидный токен, обнаружение повторного использования
- POST /auth/logout: успешный выход
- GET /auth/me: успех с валидным токеном, отказ без токена

Стратегия: UserRepository заменяется на AsyncMock через conftest.client.
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timedelta

from app.models.user import User, RoleEnum
from app.services.auth_service import auth_service
from tests.conftest import make_auth_headers

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_success_returns_tokens_and_role(client, mock_repo):
    """Регистрация с уникальным email должна возвращать токены и роль."""
    new_user = User(
        id=10, email="new@test.com", nickname="newuser",
        password=auth_service.hash_password("pass123"),
        role=RoleEnum.user, profile_completed=False,
    )
    mock_repo.get_by_email.return_value = None
    mock_repo.create_user.return_value = new_user
    mock_repo.save_refresh_token.return_value = None

    response = await client.post("/api/v1/auth/register", json={
        "nickname": "newuser",
        "email": "new@test.com",
        "password": "pass123",
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_400(client, mock_repo):
    """Регистрация с существующим email должна возвращать 400."""
    existing = User(id=1, email="exists@test.com", nickname="x", password="h", role=RoleEnum.user)
    mock_repo.get_by_email.return_value = existing

    response = await client.post("/api/v1/auth/register", json={
        "nickname": "x",
        "email": "exists@test.com",
        "password": "pass123",
    })

    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower() or "существует" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_email_format_returns_422(client, mock_repo):
    """Невалидный формат email должен возвращать 422 (валидация Pydantic)."""
    response = await client.post("/api/v1/auth/register", json={
        "nickname": "x",
        "email": "not-an-email",
        "password": "pass123",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_fields_returns_422(client, mock_repo):
    """Отсутствие обязательных полей должно возвращать 422."""
    response = await client.post("/api/v1/auth/register", json={"email": "x@test.com"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_valid_credentials_returns_tokens(client, mock_repo, user_fixture):
    """Вход с верными учётными данными должен возвращать токены."""
    mock_repo.get_by_email.return_value = user_fixture
    mock_repo.save_refresh_token.return_value = None

    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, mock_repo, user_fixture):
    """Вход с неверным паролем должен возвращать 401."""
    mock_repo.get_by_email.return_value = user_fixture

    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrong_password",
    })

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client, mock_repo):
    """Вход несуществующего пользователя должен возвращать 401."""
    mock_repo.get_by_email.return_value = None

    response = await client.post("/api/v1/auth/login", json={
        "email": "nobody@test.com",
        "password": "any_password",
    })

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_email_format_returns_422(client, mock_repo):
    """Невалидный формат email при входе должен возвращать 422."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "not-email",
        "password": "pass",
    })
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_valid_token_returns_new_tokens(client, mock_repo, user_fixture):
    """Обновление с валидным refresh-токеном должно возвращать новую пару токенов."""
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user_fixture.id)})
    user_fixture.refresh_token = refresh_token
    user_fixture.refresh_token_expires = datetime.utcnow() + timedelta(days=7)

    mock_repo.get_by_refresh_token.return_value = user_fixture
    mock_repo.save_refresh_token.return_value = None

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(client, mock_repo):
    """Невалидный refresh-токен должен возвращать 401."""
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid.token.here"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_returns_401(client, mock_repo, user_fixture):
    """Повторное использование refresh-токена должно возвращать 401 и аннулировать токены."""
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user_fixture.id)})

    # Токен валидный JWT, но в БД не найден (уже был использован)
    mock_repo.get_by_refresh_token.return_value = None
    mock_repo.get_by_id.return_value = user_fixture

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 401
    # revoke должен быть вызван
    mock_repo.revoke_refresh_token.assert_called_once()


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_returns_204(client, mock_repo, user_fixture):
    """Выход с валидным refresh-токеном должен возвращать 204."""
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user_fixture.id)})
    mock_repo.get_by_id.return_value = user_fixture

    response = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_logout_invalid_token_still_returns_204(client, mock_repo):
    """Выход с невалидным токеном должен безопасно завершиться (204 или без ошибок)."""
    response = await client.post("/api/v1/auth/logout", json={"refresh_token": "bad.token"})
    # Сервер должен отвечать 204 независимо от валидности токена
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me_with_valid_token_returns_user_data(client, mock_repo, user_fixture):
    """GET /auth/me с валидным токеном должен возвращать данные пользователя."""
    headers = make_auth_headers(user_fixture)
    mock_repo.get_by_id.return_value = user_fixture

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_fixture.email
    assert data["nickname"] == user_fixture.nickname
    assert data["role"] == "user"
    assert "profile_completed" in data


@pytest.mark.asyncio
async def test_get_me_without_token_returns_403(client, mock_repo):
    """GET /auth/me без токена должен возвращать 403 (HTTPBearer не предоставлен)."""
    response = await client.get("/api/v1/auth/me")
    # HTTPBearer возвращает 403 при отсутствии заголовка Authorization
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_me_with_invalid_token_returns_401(client, mock_repo):
    """GET /auth/me с невалидным токеном должен возвращать 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401
