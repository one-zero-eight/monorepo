__all__ = ["images_repo"]

import io
from urllib.parse import urlunsplit

from minio import Minio

from src.common_minio import MinioStore
from src.events.config import settings


class ImagesRepo:
    """Event image object names and MinIO I/O. Call :meth:`post_init` from app lifespan with a live wrapper."""

    def __init__(self) -> None:
        self._minio_store: MinioStore | None = None

    def post_init(self, minio_store: MinioStore) -> None:
        self._minio_store = minio_store

    @property
    def minio_client(self) -> Minio:
        if self._minio_store is None:  # pragma: no cover
            raise RuntimeError("ImagesRepo.post_init was not called from app lifespan")
        return self._minio_store.client

    @property
    def bucket(self) -> str:
        if self._minio_store is None:  # pragma: no cover
            raise RuntimeError("ImagesRepo.post_init was not called from app lifespan")
        return self._minio_store.bucket_name

    def get_object_name(self, image_id: str) -> str:
        return f"{settings.images_prefix}{image_id}"

    def get_url(self, image_id: str) -> str:
        mc = self.minio_client
        object_name = self.get_object_name(image_id)
        return urlunsplit(
            mc._base_url.build(
                method="GET",
                region=mc._get_region(self.bucket),
                bucket_name=self.bucket,
                object_name=object_name,
            )
        )

    def put(self, image_id: str, data: bytes, content_type: str) -> None:
        self.minio_client.put_object(
            bucket_name=self.bucket,
            object_name=self.get_object_name(image_id),
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )


images_repo = ImagesRepo()
