"""Object storage client for S3/MinIO presigned URL operations."""

from datetime import timedelta

import aioboto3

from app.core.config import settings

_session: aioboto3.Session | None = None


def get_s3_session() -> aioboto3.Session:
    """Get or create the aioboto3 session."""
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


def _get_client_kwargs() -> dict:
    """Build the kwargs for the S3 client based on configuration."""
    kwargs: dict = {
        "region_name": settings.storage_region,
        "aws_access_key_id": settings.storage_access_key_id,
        "aws_secret_access_key": settings.storage_secret_access_key,
    }
    if settings.storage_provider == "minio":
        protocol = "https" if settings.storage_use_ssl else "http"
        kwargs["endpoint_url"] = f"{protocol}://{settings.storage_endpoint}"
    return kwargs


async def generate_presigned_upload_url(
    key: str,
    content_type: str = "application/octet-stream",
    expires_in: timedelta = timedelta(minutes=15),
) -> str:
    """Generate a presigned URL for uploading a file to S3/MinIO."""
    session = get_s3_session()
    async with session.client("s3", **_get_client_kwargs()) as s3:
        url = await s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.storage_bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=int(expires_in.total_seconds()),
        )
    return url


async def generate_presigned_download_url(
    key: str,
    expires_in: timedelta = timedelta(minutes=60),
) -> str:
    """Generate a presigned URL for downloading a file from S3/MinIO."""
    session = get_s3_session()
    async with session.client("s3", **_get_client_kwargs()) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.storage_bucket,
                "Key": key,
            },
            ExpiresIn=int(expires_in.total_seconds()),
        )
    return url


async def delete_object(key: str) -> None:
    """Delete an object from S3/MinIO."""
    session = get_s3_session()
    async with session.client("s3", **_get_client_kwargs()) as s3:
        await s3.delete_object(Bucket=settings.storage_bucket, Key=key)


async def ensure_bucket() -> None:
    """Create the storage bucket if it does not exist (MinIO only)."""
    if settings.storage_provider == "s3":
        return
    session = get_s3_session()
    async with session.client("s3", **_get_client_kwargs()) as s3:
        try:
            await s3.head_bucket(Bucket=settings.storage_bucket)
        except Exception:
            await s3.create_bucket(Bucket=settings.storage_bucket)
