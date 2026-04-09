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

def test_hash_password_creates_valid_bcrypt_hash():
    hashed = auth_service.hash_password("secret")
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")


def test_hash_password_produces_unique_salts():
    h1 = auth_service.hash_password("same_password")
    h2 = auth_service.hash_password("same_password")
    assert h1 != h2


def test_verify_password_valid_credentials():
    plain = "my_password"
    hashed = auth_service.hash_password(plain)
    assert auth_service.verify_password(plain, hashed) is True


def test_verify_password_wrong_password_returns_false():
    hashed = auth_service.hash_password("correct_password")
    assert auth_service.verify_password("wrong_password", hashed) is False


def test_verify_password_empty_hash_returns_false():
    assert auth_service.verify_password("password", "") is False
    assert auth_service.verify_password("password", None) is False  # type: ignore

def test_create_access_token_contains_sub_and_role():
    token = auth_service.create_access_token(
        data={"sub": "42", "role": "user"}
    )
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "42"
    assert payload["role"] == "user"


def test_create_access_token_expires_within_expected_delta():
    token = auth_service.create_access_token(data={"sub": "1"})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    exp = datetime.utcfromtimestamp(payload["exp"])
    now = datetime.utcnow()
    max_exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES + 1)
    assert exp <= max_exp


def test_create_access_token_custom_expiry():
    delta = timedelta(seconds=10)
    token = auth_service.create_access_token(data={"sub": "1"}, expires_delta=delta)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    exp = datetime.utcfromtimestamp(payload["exp"])
    assert exp < datetime.utcnow() + timedelta(seconds=20)


def test_create_refresh_token_is_valid_jwt():
    token = auth_service.create_refresh_token(data={"sub": "7"})
    payload = jwt.decode(
        token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert payload["sub"] == "7"

@pytest.mark.asyncio
async def test_authenticate_user_success():
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
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email.return_value = None

    result = await auth_service.authenticate_user(
        repo, UserLogin(email="unknown@test.com", password="any")
    )
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password_returns_none():
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

@pytest.mark.asyncio
async def test_register_user_existing_email_raises_400():
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
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email.return_value = None

    new_user = User(id=99, email="new@test.com", nickname="newbie", password="hashed", role=RoleEnum.user)
    repo.create_user.return_value = new_user

    result = await auth_service.register_user(
        repo, UserRegister(nickname="newbie", email="new@test.com", password="password123")
    )
    assert result.email == "new@test.com"
    assert repo.create_user.called

@pytest.mark.asyncio
async def test_rotate_refresh_token_reuse_detection_revokes_all_tokens():
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
    repo = AsyncMock(spec=UserRepository)
    result = await auth_service.rotate_refresh_token(repo, "invalid.token.value")
    assert result is None

@pytest.mark.asyncio
async def test_logout_user_revokes_refresh_token():
    user = User(id=1, email="u@test.com", nickname="u", password="h", role=RoleEnum.user)
    token = auth_service.create_refresh_token(data={"sub": "1"})

    repo = AsyncMock(spec=UserRepository)
    repo.get_by_id.return_value = user

    result = await auth_service.logout_user(repo, token)

    assert result is True
    repo.revoke_refresh_token.assert_called_once_with(user)


@pytest.mark.asyncio
async def test_logout_user_invalid_token_returns_false():
    repo = AsyncMock(spec=UserRepository)
    result = await auth_service.logout_user(repo, "bad.token")
    assert result is False
