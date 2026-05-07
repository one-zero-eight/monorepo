import io
from urllib.parse import urlunsplit

from src.config import settings
from src.storages.minio import minio_client


def get_club_logo_object_name(logo_file_id: str, size: int | None = None):
    size_postfix = f"-{size}" if size else ""
    return f"{settings.minio.club_logos_prefix}{logo_file_id}{size_postfix}"


def get_club_logo_url(logo_file_id: str, size: int | None = None):
    object_name = get_club_logo_object_name(logo_file_id, size)
    # Build public URL
    return urlunsplit(
        minio_client._base_url.build(
            method="GET",
            region=minio_client._get_region(settings.minio.bucket),
            bucket_name=settings.minio.bucket,
            object_name=object_name,
        )
    )


def put_club_logo(logo_file_id: str, size: int | None, data: bytes, content_type: str):
    object_name = get_club_logo_object_name(logo_file_id, size)
    minio_client.put_object(
        bucket_name=settings.minio.bucket,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
