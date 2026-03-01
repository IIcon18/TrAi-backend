import uuid
from contextlib import asynccontextmanager
from fastapi import UploadFile, HTTPException
from app.core.config import settings

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "application/pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_session():
    import aiobotocore.session
    session = aiobotocore.session.get_session()
    return session.create_client(
        "s3",
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


async def ensure_bucket_exists() -> None:
    async with _get_session() as client:
        try:
            await client.head_bucket(Bucket=settings.MINIO_BUCKET)
        except Exception:
            await client.create_bucket(Bucket=settings.MINIO_BUCKET)


def validate_file(file: UploadFile, content: bytes) -> None:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{file.content_type}' is not allowed. Allowed: JPEG, PNG, GIF, PDF.",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds 10 MB limit.",
        )


async def upload_file(file: UploadFile) -> tuple[str, str, int]:
    """Upload file to MinIO. Returns (s3_key, content_type, size)."""
    content = await file.read()
    validate_file(file, content)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    s3_key = f"{uuid.uuid4().hex}.{ext}"

    async with _get_session() as client:
        await client.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=s3_key,
            Body=content,
            ContentType=file.content_type,
        )

    return s3_key, file.content_type, len(content)


async def generate_presigned_url(s3_key: str, expires: int = 3600) -> str:
    """Generate a pre-signed URL valid for `expires` seconds."""
    async with _get_session() as client:
        url = await client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET, "Key": s3_key},
            ExpiresIn=expires,
        )
    return url


async def delete_file(s3_key: str) -> None:
    """Delete an object from MinIO."""
    async with _get_session() as client:
        await client.delete_object(Bucket=settings.MINIO_BUCKET, Key=s3_key)
