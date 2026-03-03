"""
Интеграционные тесты эндпоинтов /api/v1/admin/*.

Фокус: проверка RBAC-ограничений (admin-only), фильтрация, пагинация.

Сценарии:
- GET /admin/users: доступен только admin, возвращает список + пагинацию
- GET /admin/users/{id}: admin — 200, admin сам себя — 200, несуществующий — 404
- PUT /admin/users/{id}/role: смена роли admin-ом, запрет самоизменения
- DELETE /admin/users/{id}: удаление admin-ом, запрет самоудаления
- RBAC: 403 для user, 403 для pro, 401 без токена
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from app.models.user import User, RoleEnum
from tests.conftest import make_auth_headers

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Вспомогательная функция для настройки mock_db
# ---------------------------------------------------------------------------

def setup_mock_db_for_user_list(mock_db, users: list, total: int):
    """
    Настроить mock_db для двойного вызова db.execute:
    1-й — COUNT, 2-й — список пользователей.
    """
    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = users

    mock_db.execute.side_effect = [count_result, users_result]


def setup_mock_db_for_single_user(mock_db, user):
    """Настроить mock_db для запроса одного пользователя."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = result


# ---------------------------------------------------------------------------
# RBAC: проверка прав доступа
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_users_as_admin_returns_200(admin_client, mock_db, admin_fixture):
    """Администратор должен получать список пользователей (200)."""
    setup_mock_db_for_user_list(mock_db, [admin_fixture], total=1)

    response = await admin_client.get("/api/v1/admin/users")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data


@pytest.mark.asyncio
async def test_get_users_as_user_returns_403(user_client):
    """Обычный пользователь должен получать 403 при попытке доступа к /admin/users."""
    response = await user_client.get("/api/v1/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_users_as_pro_returns_403(pro_client):
    """Pro-пользователь должен получать 403 при попытке доступа к /admin/users."""
    response = await pro_client.get("/api/v1/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_users_without_token_returns_403(client, mock_repo):
    """Запрос без токена должен возвращать 403 (HTTPBearer отсутствует)."""
    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/users?search=&role=&page=&page_size=
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_users_pagination_structure(admin_client, mock_db, admin_fixture, user_fixture):
    """Ответ должен содержать корректную структуру пагинации."""
    setup_mock_db_for_user_list(mock_db, [admin_fixture, user_fixture], total=2)

    response = await admin_client.get("/api/v1/admin/users?page=1&page_size=10")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_users_empty_result_returns_200(admin_client, mock_db):
    """Пустой список пользователей должен возвращать 200 с items=[]."""
    setup_mock_db_for_user_list(mock_db, [], total=0)

    response = await admin_client.get("/api/v1/admin/users")

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_users_invalid_role_filter_returns_400(admin_client, mock_db):
    """Невалидный фильтр роли должен возвращать 400."""
    # Сначала настроим mock так, чтобы запрос дошёл до валидации role
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    mock_db.execute.return_value = count_result

    response = await admin_client.get("/api/v1/admin/users?role=superadmin")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /admin/users/{user_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_by_id_as_admin_returns_200(admin_client, mock_db, user_fixture):
    """Admin должен получать данные пользователя по ID."""
    setup_mock_db_for_single_user(mock_db, user_fixture)

    response = await admin_client.get(f"/api/v1/admin/users/{user_fixture.id}")

    assert response.status_code == 200
    assert response.json()["email"] == user_fixture.email


@pytest.mark.asyncio
async def test_get_user_by_id_not_found_returns_404(admin_client, mock_db):
    """Несуществующий пользователь должен возвращать 404."""
    setup_mock_db_for_single_user(mock_db, None)

    response = await admin_client.get("/api/v1/admin/users/99999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /admin/users/{user_id}/role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_user_role_as_admin_success(admin_client, mock_db, user_fixture):
    """Admin должен успешно менять роль другого пользователя."""
    setup_mock_db_for_single_user(mock_db, user_fixture)

    response = await admin_client.put(
        f"/api/v1/admin/users/{user_fixture.id}/role",
        json={"role": "pro"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["new_role"] == "pro"


@pytest.mark.asyncio
async def test_change_user_role_as_user_returns_403(user_client, user_fixture):
    """Обычный пользователь не должен менять роли."""
    response = await user_client.put(
        f"/api/v1/admin/users/1/role",
        json={"role": "admin"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_change_own_role_returns_400(admin_client, mock_db, admin_fixture):
    """Admin не должен иметь возможность изменить свою собственную роль."""
    response = await admin_client.put(
        f"/api/v1/admin/users/{admin_fixture.id}/role",
        json={"role": "user"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_role_invalid_value_returns_400(admin_client, mock_db, user_fixture):
    """Недопустимое значение роли должно возвращать 400."""
    setup_mock_db_for_single_user(mock_db, user_fixture)

    response = await admin_client.put(
        f"/api/v1/admin/users/{user_fixture.id}/role",
        json={"role": "superadmin"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /admin/users/{user_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_user_as_admin_success(admin_client, mock_db, user_fixture):
    """Admin должен успешно удалять другого пользователя."""
    setup_mock_db_for_single_user(mock_db, user_fixture)

    response = await admin_client.delete(f"/api/v1/admin/users/{user_fixture.id}")

    assert response.status_code == 200
    assert "удалён" in response.json()["message"].lower() or "deleted" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_delete_user_as_user_returns_403(user_client, user_fixture):
    """Обычный пользователь не должен иметь возможности удалять пользователей."""
    response = await user_client.delete(f"/api/v1/admin/users/{user_fixture.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_self_as_admin_returns_400(admin_client, admin_fixture):
    """Admin не должен иметь возможности удалить самого себя."""
    response = await admin_client.delete(f"/api/v1/admin/users/{admin_fixture.id}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_nonexistent_user_returns_404(admin_client, mock_db):
    """Удаление несуществующего пользователя должно возвращать 404."""
    setup_mock_db_for_single_user(mock_db, None)

    response = await admin_client.delete("/api/v1/admin/users/99999")

    assert response.status_code == 404
