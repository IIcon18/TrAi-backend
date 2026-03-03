"""
Модульные тесты для S3Service (MinIO).

Тестируются:
- validate_file: допустимые типы, превышение размера, граничный случай
- upload_file: успешная загрузка (mock aiobotocore), генерация ключа
- generate_presigned_url: вызов S3 клиента с правильными параметрами
- delete_file: вызов delete_object

Стратегия: _get_session() мокируется через pytest-mock,
чтобы исключить реальное подключение к MinIO.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, UploadFile
from io import BytesIO

from app.services.s3_service import validate_file, upload_file, generate_presigned_url, delete_file, MAX_FILE_SIZE

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------

def make_upload_file(
    filename: str = "test.jpg",
    content_type: str = "image/jpeg",
    content: bytes = b"fake_image_data",
) -> UploadFile:
    """Создать мок UploadFile с заданными параметрами."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.read = AsyncMock(return_value=content)
    return mock_file


def make_s3_client_mock() -> tuple:
    """Вернуть (mock_client, mock_context_manager) для патчинга _get_session."""
    mock_client = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_client, mock_cm


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------

def test_validate_file_jpeg_passes():
    """image/jpeg должен проходить валидацию."""
    f = make_upload_file(content_type="image/jpeg", content=b"x" * 100)
    validate_file(f, b"x" * 100)  # не должно бросать исключение


@pytest.mark.parametrize("content_type", ["image/jpeg", "image/png", "image/gif", "application/pdf"])
def test_validate_file_allowed_types_pass(content_type: str):
    """Все разрешённые типы файлов должны проходить валидацию без исключений."""
    f = make_upload_file(content_type=content_type, content=b"data")
    validate_file(f, b"data")  # не должно бросать исключение


def test_validate_file_invalid_type_raises_415():
    """Запрещённый тип файла должен вызывать HTTPException 415."""
    f = make_upload_file(content_type="text/plain", content=b"text")
    with pytest.raises(HTTPException) as exc_info:
        validate_file(f, b"text")
    assert exc_info.value.status_code == 415


def test_validate_file_invalid_type_exe_raises_415():
    """application/exe должен вызывать HTTPException 415."""
    f = make_upload_file(content_type="application/x-executable", content=b"binary")
    with pytest.raises(HTTPException) as exc_info:
        validate_file(f, b"binary")
    assert exc_info.value.status_code == 415


def test_validate_file_oversized_raises_413():
    """Файл размером > 10 MB должен вызывать HTTPException 413."""
    oversized = b"x" * (MAX_FILE_SIZE + 1)
    f = make_upload_file(content_type="image/jpeg", content=oversized)
    with pytest.raises(HTTPException) as exc_info:
        validate_file(f, oversized)
    assert exc_info.value.status_code == 413


def test_validate_file_exactly_max_size_passes():
    """Файл ровно в 10 MB должен проходить валидацию (граничное значение включительно)."""
    exactly_max = b"x" * MAX_FILE_SIZE
    f = make_upload_file(content_type="image/jpeg", content=exactly_max)
    validate_file(f, exactly_max)  # не должно бросать исключение


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_file_calls_put_object_with_correct_bucket():
    """upload_file должен вызвать put_object с правильным Bucket."""
    from app.core.config import settings

    mock_client, mock_cm = make_s3_client_mock()

    with patch("app.services.s3_service._get_session", return_value=mock_cm):
        f = make_upload_file(filename="photo.jpg", content_type="image/jpeg", content=b"img")
        s3_key, content_type, size = await upload_file(f)

    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == settings.MINIO_BUCKET
    assert call_kwargs["ContentType"] == "image/jpeg"


@pytest.mark.asyncio
async def test_upload_file_returns_key_content_type_size():
    """upload_file должен возвращать кортеж (s3_key, content_type, size)."""
    mock_client, mock_cm = make_s3_client_mock()
    content = b"fake_image"

    with patch("app.services.s3_service._get_session", return_value=mock_cm):
        f = make_upload_file(filename="photo.png", content_type="image/png", content=content)
        s3_key, content_type, size = await upload_file(f)

    assert isinstance(s3_key, str)
    assert s3_key.endswith(".png")
    assert content_type == "image/png"
    assert size == len(content)


@pytest.mark.asyncio
async def test_upload_file_invalid_type_raises_415_before_s3():
    """upload_file должен бросать 415 до обращения к S3 при запрещённом типе."""
    mock_client, mock_cm = make_s3_client_mock()

    with patch("app.services.s3_service._get_session", return_value=mock_cm):
        f = make_upload_file(content_type="video/mp4", content=b"video")
        with pytest.raises(HTTPException) as exc_info:
            await upload_file(f)

    assert exc_info.value.status_code == 415
    mock_client.put_object.assert_not_called()


# ---------------------------------------------------------------------------
# generate_presigned_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_presigned_url_returns_url():
    """generate_presigned_url должен вернуть строку URL."""
    mock_client, mock_cm = make_s3_client_mock()
    expected_url = "http://minio:9000/trai-attachments/key.jpg?X-Amz-Signature=abc"
    mock_client.generate_presigned_url.return_value = expected_url

    with patch("app.services.s3_service._get_session", return_value=mock_cm):
        url = await generate_presigned_url("key.jpg", expires=3600)

    assert url == expected_url
    mock_client.generate_presigned_url.assert_called_once()


@pytest.mark.asyncio
async def test_generate_presigned_url_passes_correct_expiry():
    """generate_presigned_url должен передавать ExpiresIn=3600 в S3 клиент."""
    mock_client, mock_cm = make_s3_client_mock()
    mock_client.generate_presigned_url.return_value = "http://url"

    with patch("app.services.s3_service._get_session", return_value=mock_cm):
        await generate_presigned_url("some_key.pdf", expires=3600)

    call_kwargs = mock_client.generate_presigned_url.call_args.kwargs
    assert call_kwargs["ExpiresIn"] == 3600


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_file_calls_delete_object():
    """delete_file должен вызвать delete_object с правильным ключом."""
    from app.core.config import settings

    mock_client, mock_cm = make_s3_client_mock()

    with patch("app.services.s3_service._get_session", return_value=mock_cm):
        await delete_file("my_key.jpg")

    mock_client.delete_object.assert_called_once_with(
        Bucket=settings.MINIO_BUCKET, Key="my_key.jpg"
    )
