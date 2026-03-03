"""
Модульные тесты для AuthService.

Покрываемые методы:
- hash_password / verify_password
- create_access_token / create_refresh_token
- authenticate_user
- register_user
- rotate_refresh_token (включая обнаружение повторного использования)
- logout_user
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from jose import jwt
from fastapi import HTTPException

from app.services.auth_service import auth_service, AuthService
from app.core.config import settings
from app.models.user import User, RoleEnum
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserLogin, UserRegister

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------

def test_hash_password_creates_valid_bcrypt_hash():
    """hash_password должен возвращать непустую строку, начинающуюся с $2b$."""
    hashed = auth_service.hash_password("secret")
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")


def test_hash_password_produces_unique_salts():
    """Два хэша одного пароля должны отличаться (уникальные соли bcrypt)."""
    h1 = auth_service.hash_password("same_password")
    h2 = auth_service.hash_password("same_password")
    assert h1 != h2


def test_verify_password_valid_credentials():
    """verify_password возвращает True для верного пароля."""
    plain = "my_password"
    hashed = auth_service.hash_password(plain)
    assert auth_service.verify_password(plain, hashed) is True


def test_verify_password_wrong_password_returns_false():
    """verify_password возвращает False для неверного пароля."""
    hashed = auth_service.hash_password("correct_password")
    assert auth_service.verify_password("wrong_password", hashed) is False


def test_verify_password_empty_hash_returns_false():
    """verify_password возвращает False, если хэш пустой или None."""
    assert auth_service.verify_password("password", "") is False
    assert auth_service.verify_password("password", None) is False  # type: ignore


# ---------------------------------------------------------------------------
# create_access_token / create_refresh_token
# ---------------------------------------------------------------------------

def test_create_access_token_contains_sub_and_role():
    """Access-токен должен содержать поля sub и role."""
    token = auth_service.create_access_token(
        data={"sub": "42", "role": "user"}
    )
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "42"
    assert payload["role"] == "user"


def test_create_access_token_expires_within_expected_delta():
    """Access-токен должен истекать не позже чем через ACCESS_TOKEN_EXPIRE_MINUTES + 1 мин."""
    token = auth_service.create_access_token(data={"sub": "1"})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    exp = datetime.utcfromtimestamp(payload["exp"])
    now = datetime.utcnow()
    max_exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES + 1)
    assert exp <= max_exp


def test_create_access_token_custom_expiry():
    """Access-токен с кастомным сроком действия должен его соблюдать."""
    delta = timedelta(seconds=10)
    token = auth_service.create_access_token(data={"sub": "1"}, expires_delta=delta)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    exp = datetime.utcfromtimestamp(payload["exp"])
    assert exp < datetime.utcnow() + timedelta(seconds=20)


def test_create_refresh_token_is_valid_jwt():
    """Refresh-токен должен быть валидным JWT, подписанным REFRESH_SECRET_KEY."""
    token = auth_service.create_refresh_token(data={"sub": "7"})
    payload = jwt.decode(
        token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert payload["sub"] == "7"


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticate_user_success():
    """authenticate_user возвращает пользователя при верных учётных данных."""
    plain_password = "pass123"
    user = User(
        id=1,
        email="u@test.com",
        nickname="u",
        password=auth_service.hash_password(plain_password),
        role=RoleEnum.user,
    )
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email.return_value = user

    result = await auth_service.authenticate_user(
        repo, UserLogin(email="u@test.com", password=plain_password)
    )
    assert result == user


@pytest.mark.asyncio
async def test_authenticate_user_user_not_found_returns_none():
    """authenticate_user возвращает None, если пользователь не найден."""
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email.return_value = None

    result = await auth_service.authenticate_user(
        repo, UserLogin(email="unknown@test.com", password="any")
    )
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password_returns_none():
    """authenticate_user возвращает None при неверном пароле."""
    user = User(
        id=1,
        email="u@test.com",
        nickname="u",
        password=auth_service.hash_password("correct"),
        role=RoleEnum.user,
    )
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email.return_value = user

    result = await auth_service.authenticate_user(
        repo, UserLogin(email="u@test.com", password="wrong")
    )
    assert result is None


# ---------------------------------------------------------------------------
# register_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_user_existing_email_raises_400():
    """register_user выбрасывает HTTP 400, если email уже существует."""
    existing = User(id=1, email="exists@test.com", nickname="x", password="hashed", role=RoleEnum.user)
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email.return_value = existing

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register_user(
            repo, UserRegister(nickname="new", email="exists@test.com", password="pass123")
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_register_user_creates_new_user():
    """register_user создаёт и возвращает нового пользователя при уникальном email."""
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email.return_value = None

    new_user = User(id=99, email="new@test.com", nickname="newbie", password="hashed", role=RoleEnum.user)
    repo.create_user.return_value = new_user

    result = await auth_service.register_user(
        repo, UserRegister(nickname="newbie", email="new@test.com", password="password123")
    )
    assert result.email == "new@test.com"
    assert repo.create_user.called


# ---------------------------------------------------------------------------
# rotate_refresh_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rotate_refresh_token_reuse_detection_revokes_all_tokens():
    """
    Если JWT валиден, но токена нет в БД → обнаружение повторного использования.
    Должен быть вызван revoke_refresh_token для пострадавшего пользователя.
    """
    victim = User(id=5, email="victim@test.com", nickname="v", password="h", role=RoleEnum.user)
    presented_token = auth_service.create_refresh_token(data={"sub": "5"})

    repo = AsyncMock(spec=UserRepository)
    # Токен подписан верно, но в БД не найден (уже использован)
    repo.get_by_refresh_token.return_value = None
    repo.get_by_id.return_value = victim

    result = await auth_service.rotate_refresh_token(repo, presented_token)

    assert result is None
    repo.revoke_refresh_token.assert_called_once_with(victim)


@pytest.mark.asyncio
async def test_rotate_refresh_token_expired_db_record_returns_none():
    """rotate_refresh_token возвращает None, если срок действия токена в БД истёк."""
    user = User(
        id=1,
        email="u@test.com",
        nickname="u",
        password="h",
        role=RoleEnum.user,
        refresh_token_expires=datetime.utcnow() - timedelta(days=1),  # истёк
    )
    presented_token = auth_service.create_refresh_token(data={"sub": "1"})
    user.refresh_token = presented_token

    repo = AsyncMock(spec=UserRepository)
    repo.get_by_refresh_token.return_value = user

    result = await auth_service.rotate_refresh_token(repo, presented_token)
    assert result is None


@pytest.mark.asyncio
async def test_rotate_refresh_token_invalid_jwt_returns_none():
    """rotate_refresh_token возвращает None при невалидной подписи JWT."""
    repo = AsyncMock(spec=UserRepository)
    result = await auth_service.rotate_refresh_token(repo, "invalid.token.value")
    assert result is None


# ---------------------------------------------------------------------------
# logout_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_user_revokes_refresh_token():
    """logout_user должен вызвать revoke_refresh_token для корректного токена."""
    user = User(id=1, email="u@test.com", nickname="u", password="h", role=RoleEnum.user)
    token = auth_service.create_refresh_token(data={"sub": "1"})

    repo = AsyncMock(spec=UserRepository)
    repo.get_by_id.return_value = user

    result = await auth_service.logout_user(repo, token)

    assert result is True
    repo.revoke_refresh_token.assert_called_once_with(user)


@pytest.mark.asyncio
async def test_logout_user_invalid_token_returns_false():
    """logout_user возвращает False при невалидном JWT."""
    repo = AsyncMock(spec=UserRepository)
    result = await auth_service.logout_user(repo, "bad.token")
    assert result is False
