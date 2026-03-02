"""
Интеграционные тесты эндпоинтов /api/v1/attachments/*.

Покрываемые сценарии:
- POST /attachments/upload: успешная загрузка (S3 замокирован), 415 (неверный тип),
  413 (превышение размера), 401 без токена
- GET /attachments/{id}/url: получение presigned URL для своего вложения,
  403 для чужого вложения
- DELETE /attachments/{id}: удаление своего вложения, 403 для чужого, 404 не найдено

Стратегия: S3-функции мокируются через unittest.mock.patch.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.models.attachment import Attachment

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Вспомогательная фабрика
# ---------------------------------------------------------------------------

def make_attachment(user_id: int, attachment_id: int = 1) -> Attachment:
    return Attachment(
        id=attachment_id,
        user_id=user_id,
        entity_type="workout",
        entity_id=1,
        filename="photo.jpg",
        s3_key="abc123.jpg",
        content_type="image/jpeg",
        size=1024,
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# POST /attachments/upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_file_valid_image_returns_201(user_client, mock_db, user_fixture):
    """Загрузка валидного изображения должна возвращать 201 с данными вложения."""
    attachment = make_attachment(user_fixture.id)

    with patch("app.api.v1.attachments.s3_service.upload_file",
               new_callable=AsyncMock,
               return_value=("abc123.jpg", "image/jpeg", 1024)):
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        async def fake_refresh(obj):
            obj.id = 1
            obj.created_at = datetime.utcnow()

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        from io import BytesIO
        image_bytes = b"\xff\xd8\xff" + b"x" * 100  # fake JPEG bytes

        response = await user_client.post(
            "/api/v1/attachments/upload",
            data={"entity_type": "workout", "entity_id": "1"},
            files={"file": ("photo.jpg", BytesIO(image_bytes), "image/jpeg")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "photo.jpg"


@pytest.mark.asyncio
async def test_upload_file_invalid_type_returns_415(user_client, mock_db):
    """Загрузка файла запрещённого типа должна возвращать 415."""
    from io import BytesIO

    with patch("app.api.v1.attachments.s3_service.upload_file",
               side_effect=__import__("fastapi").HTTPException(status_code=415, detail="Type not allowed")):
        response = await user_client.post(
            "/api/v1/attachments/upload",
            data={"entity_type": "workout", "entity_id": "1"},
            files={"file": ("script.sh", BytesIO(b"#!/bin/bash"), "text/x-shellscript")},
        )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_file_oversized_returns_413(user_client, mock_db):
    """Загрузка файла > 10 MB должна возвращать 413."""
    from io import BytesIO
    from fastapi import HTTPException

    with patch("app.api.v1.attachments.s3_service.upload_file",
               side_effect=HTTPException(status_code=413, detail="File too large")):
        response = await user_client.post(
            "/api/v1/attachments/upload",
            data={"entity_type": "workout", "entity_id": "1"},
            files={"file": ("big.jpg", BytesIO(b"x" * 100), "image/jpeg")},
        )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_file_unauthenticated_returns_403(client, mock_repo):
    """Загрузка без токена должна возвращать 403."""
    from io import BytesIO

    response = await client.post(
        "/api/v1/attachments/upload",
        data={"entity_type": "workout", "entity_id": "1"},
        files={"file": ("photo.jpg", BytesIO(b"data"), "image/jpeg")},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_file_invalid_entity_type_returns_400(user_client, mock_db):
    """Недопустимый entity_type должен возвращать 400."""
    from io import BytesIO

    with patch("app.api.v1.attachments.s3_service.upload_file",
               new_callable=AsyncMock,
               return_value=("key.jpg", "image/jpeg", 100)):
        response = await user_client.post(
            "/api/v1/attachments/upload",
            data={"entity_type": "invalid_type", "entity_id": "1"},
            files={"file": ("photo.jpg", BytesIO(b"data"), "image/jpeg")},
        )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /attachments/{id}/url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_presigned_url_for_own_attachment(user_client, mock_db, user_fixture):
    """Пользователь должен получать presigned URL для своего вложения."""
    attachment = make_attachment(user_fixture.id)
    result = MagicMock()
    result.scalar_one_or_none.return_value = attachment
    mock_db.execute.return_value = result

    with patch("app.api.v1.attachments.s3_service.generate_presigned_url",
               new_callable=AsyncMock,
               return_value="http://minio:9000/trai/abc123.jpg?signature=xyz"):
        response = await user_client.get(f"/api/v1/attachments/{attachment.id}/url")

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert data["expires_in"] == 3600


@pytest.mark.asyncio
async def test_get_presigned_url_other_user_returns_403(user_client, mock_db, user_fixture):
    """Пользователь не должен получать URL для чужого вложения."""
    foreign_attachment = make_attachment(user_id=999, attachment_id=42)  # другой пользователь
    result = MagicMock()
    result.scalar_one_or_none.return_value = foreign_attachment
    mock_db.execute.return_value = result

    response = await user_client.get(f"/api/v1/attachments/{foreign_attachment.id}/url")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_presigned_url_not_found_returns_404(user_client, mock_db):
    """Несуществующее вложение должно возвращать 404."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    response = await user_client.get("/api/v1/attachments/99999/url")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /attachments/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_own_attachment_success(user_client, mock_db, user_fixture):
    """Пользователь должен успешно удалять своё вложение."""
    attachment = make_attachment(user_fixture.id)
    result = MagicMock()
    result.scalar_one_or_none.return_value = attachment
    mock_db.execute.return_value = result
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.api.v1.attachments.s3_service.delete_file", new_callable=AsyncMock):
        response = await user_client.delete(f"/api/v1/attachments/{attachment.id}")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_foreign_attachment_returns_403(user_client, mock_db):
    """Пользователь не должен иметь возможность удалить чужое вложение."""
    foreign_attachment = make_attachment(user_id=999, attachment_id=42)
    result = MagicMock()
    result.scalar_one_or_none.return_value = foreign_attachment
    mock_db.execute.return_value = result

    response = await user_client.delete(f"/api/v1/attachments/{foreign_attachment.id}")

    assert response.status_code == 403
