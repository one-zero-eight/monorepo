from minio import Minio

from src.config import settings

minio_client: Minio = Minio(
    endpoint=settings.minio.endpoint,
    secure=settings.minio.secure,
    region=settings.minio.region,
    access_key=settings.minio.access_key,
    secret_key=settings.minio.secret_key.get_secret_value(),
)
