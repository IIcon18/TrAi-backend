"""
E2E тесты CRUD-операций с учётом ролевой модели.

Проверяет сквозные сценарии:
1. Обычный пользователь не может управлять другими пользователями (admin-эндпоинты)
2. Pro-пользователь не имеет доступа к admin-панели
3. Admin может просматривать любых пользователей
4. Обычный пользователь не может генерировать AI-тренировки (только pro/admin)
5. Admin может видеть вложения других пользователей (только если entity_type совпадает)

Стратегия: HTTP-клиенты с разными ролями (user_client, admin_client, pro_client).
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.models.user import User, RoleEnum
from app.models.attachment import Attachment
from tests.conftest import make_auth_headers

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Сценарий 1: Обычный пользователь не управляет пользователями
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_cannot_list_all_users(user_client):
    """Обычный пользователь не должен видеть список всех пользователей."""
    response = await user_client.get("/api/v1/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_delete_other_user(user_client):
    """Обычный пользователь не должен удалять других пользователей."""
    response = await user_client.delete("/api/v1/admin/users/999")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_change_role(user_client):
    """Обычный пользователь не должен менять роли."""
    response = await user_client.put("/api/v1/admin/users/999/role", json={"role": "admin"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Сценарий 2: Pro-пользователь не имеет доступа к admin-панели
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pro_cannot_access_admin_users(pro_client):
    """Pro-пользователь не должен иметь доступ к /admin/users."""
    response = await pro_client.get("/api/v1/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pro_cannot_delete_users(pro_client):
    """Pro-пользователь не должен иметь возможность удалять пользователей."""
    response = await pro_client.delete("/api/v1/admin/users/1")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Сценарий 3: Admin может просматривать пользователей
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_manage_all_users(admin_client, mock_db, admin_fixture, user_fixture):
    """Admin должен иметь доступ к списку пользователей и пагинации."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [admin_fixture, user_fixture]

    mock_db.execute.side_effect = [count_result, users_result]

    response = await admin_client.get("/api/v1/admin/users")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_admin_can_get_specific_user(admin_client, mock_db, user_fixture):
    """Admin должен получать данные конкретного пользователя."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = user_fixture
    mock_db.execute.return_value = result

    response = await admin_client.get(f"/api/v1/admin/users/{user_fixture.id}")

    assert response.status_code == 200
    assert response.json()["email"] == user_fixture.email


# ---------------------------------------------------------------------------
# Сценарий 4: AI-генерация тренировок (только pro/admin)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_limit_exceeded_cannot_generate_ai_workout(user_client, mock_db, user_fixture):
    """Пользователь, исчерпавший лимит AI-генераций (3/мес), получает 403."""
    user_fixture.ai_workout_uses = 3
    user_fixture.ai_workout_reset_date = datetime.utcnow()

    response = await user_client.post("/api/v1/workouts/generate-ai", json={
        "muscle_group": "upper_body_push"
    })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_generate_ai_workout(client, mock_repo):
    """Неаутентифицированный пользователь не должен иметь доступ к AI-генерации."""
    response = await client.post("/api/v1/workouts/generate-ai", json={
        "muscle_group": "lower_body"
    })
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Сценарий 5: Контроль доступа к вложениям
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_cannot_access_foreign_attachment_url(user_client, mock_db):
    """Пользователь не должен получать URL для чужого вложения."""
    foreign_attachment = Attachment(
        id=100,
        user_id=999,  # другой пользователь
        entity_type="workout",
        entity_id=1,
        filename="secret.jpg",
        s3_key="secret_key.jpg",
        content_type="image/jpeg",
        size=512,
        created_at=datetime.utcnow(),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = foreign_attachment
    mock_db.execute.return_value = result

    response = await user_client.get("/api/v1/attachments/100/url")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_any_attachment_url(admin_client, mock_db):
    """Admin должен иметь возможность получать URL для любого вложения."""
    foreign_attachment = Attachment(
        id=100,
        user_id=999,  # другой пользователь
        entity_type="workout",
        entity_id=1,
        filename="photo.jpg",
        s3_key="photo_key.jpg",
        content_type="image/jpeg",
        size=512,
        created_at=datetime.utcnow(),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = foreign_attachment
    mock_db.execute.return_value = result

    with patch("app.api.v1.attachments.s3_service.generate_presigned_url",
               new_callable=AsyncMock,
               return_value="http://minio/photo_key.jpg?sig=abc"):
        response = await admin_client.get("/api/v1/attachments/100/url")

    assert response.status_code == 200
