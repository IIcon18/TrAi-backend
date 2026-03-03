"""
E2E тесты полного цикла аутентификации.

Сценарии:
1. Полный цикл: регистрация → логин → GET /me → логаут
2. Ротация refresh-токена: старый токен аннулируется после refresh
3. Обнаружение повторного использования refresh-токена → 401 + аннулирование
4. Истечение access-токена → попытка обращения к /me → 401

Стратегия: использует полный HTTP-стек через httpx.AsyncClient.
Репозиторий мокируется (AsyncMock), без реальной БД.
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timedelta

from app.models.user import User, RoleEnum
from app.services.auth_service import auth_service

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Сценарий 1: Полный цикл регистрация → логин → /me → логаут
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_login_me_logout_flow(client, mock_repo):
    """
    E2E: Пользователь регистрируется, входит, получает данные о себе, выходит.
    Проверяем: все шаги возвращают ожидаемые статусы.
    """
    new_user = User(
        id=42,
        email="e2e@test.com",
        nickname="e2euser",
        password=auth_service.hash_password("securepass"),
        role=RoleEnum.user,
        profile_completed=False,
        created_at=datetime.utcnow(),
    )
    mock_repo.get_by_email.return_value = None
    mock_repo.create_user.return_value = new_user
    mock_repo.save_refresh_token.return_value = None

    # 1. Регистрация
    reg_response = await client.post("/api/v1/auth/register", json={
        "nickname": "e2euser",
        "email": "e2e@test.com",
        "password": "securepass",
    })
    assert reg_response.status_code == 200
    tokens = reg_response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    assert tokens["role"] == "user"

    # Сброс мока для шага логина
    mock_repo.get_by_email.return_value = new_user

    # 2. Логин
    login_response = await client.post("/api/v1/auth/login", json={
        "email": "e2e@test.com",
        "password": "securepass",
    })
    assert login_response.status_code == 200

    # 3. GET /me с токеном из регистрации
    mock_repo.get_by_id.return_value = new_user
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == "e2e@test.com"
    assert me_data["nickname"] == "e2euser"

    # 4. Логаут
    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == 204


# ---------------------------------------------------------------------------
# Сценарий 2: Ротация refresh-токена
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_token_rotation_old_token_invalidated(client, mock_repo, user_fixture):
    """
    E2E: После обновления токена старый refresh-токен не должен работать.
    Проверяем: повторный refresh со старым токеном возвращает 401.
    """
    old_refresh = auth_service.create_refresh_token(data={"sub": str(user_fixture.id)})
    new_refresh = auth_service.create_refresh_token(data={"sub": str(user_fixture.id)})

    user_fixture.refresh_token = old_refresh
    user_fixture.refresh_token_expires = datetime.utcnow() + timedelta(days=7)

    # 1-й refresh: успешный
    mock_repo.get_by_refresh_token.return_value = user_fixture
    mock_repo.save_refresh_token.return_value = None

    response1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert response1.status_code == 200
    new_tokens = response1.json()
    assert "refresh_token" in new_tokens  # новый токен выдан
    assert "access_token" in new_tokens

    # 2-й refresh: старый токен не должен работать (его нет в БД)
    mock_repo.get_by_refresh_token.return_value = None  # старый токен удалён
    mock_repo.get_by_id.return_value = user_fixture

    response2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert response2.status_code == 401


# ---------------------------------------------------------------------------
# Сценарий 3: Обнаружение повторного использования токена
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_reuse_triggers_full_revocation(client, mock_repo, user_fixture):
    """
    E2E: При обнаружении повторного использования refresh-токена
    сервер должен аннулировать все токены пользователя (вызов revoke_refresh_token).
    """
    stolen_token = auth_service.create_refresh_token(data={"sub": str(user_fixture.id)})

    # Токен валиден (JWT), но в БД не найден — значит, уже был использован
    mock_repo.get_by_refresh_token.return_value = None
    mock_repo.get_by_id.return_value = user_fixture

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": stolen_token})

    assert response.status_code == 401
    # Все токены пользователя должны быть аннулированы
    mock_repo.revoke_refresh_token.assert_called_once_with(user_fixture)


# ---------------------------------------------------------------------------
# Сценарий 4: Истечение access-токена
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_access_token_returns_401(client, mock_repo, user_fixture):
    """
    E2E: Access-токен с истекшим сроком действия должен возвращать 401.
    Проверяем: сервер отклоняет истёкший токен независимо от пользователя в БД.
    """
    expired_token = auth_service.create_access_token(
        data={"sub": str(user_fixture.id), "role": user_fixture.role.value},
        expires_delta=timedelta(seconds=-1),  # уже истёк
    )
    mock_repo.get_by_id.return_value = user_fixture

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
