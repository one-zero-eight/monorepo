__all__ = ["logos_repo"]

import io
from urllib.parse import urlunsplit

from minio import Minio

from src.clubs.config import settings
from src.common_minio import MinioStore


class LogosRepo:
    """Club logo object names and MinIO I/O. Call :meth:`post_init` from app lifespan with a live wrapper."""

    def __init__(self) -> None:
        self._minio_store: MinioStore | None = None

    def post_init(self, minio_store: MinioStore) -> None:
        self._minio_store = minio_store

    @property
    def minio_client(self) -> Minio:
        if self._minio_store is None:  # pragma: no cover
            raise RuntimeError("ClubsLogos.post_init was not called from app lifespan")
        return self._minio_store.client

    @property
    def bucket(self) -> str:
        if self._minio_store is None:  # pragma: no cover
            raise RuntimeError("ClubsLogos.post_init was not called from app lifespan")
        return self._minio_store.bucket_name

    def get_club_logo_object_name(self, logo_file_id: str, size: int | None = None) -> str:
        size_postfix = f"-{size}" if size else ""
        return f"{settings.minio.club_logos_prefix}{logo_file_id}{size_postfix}"

    def get_club_logo_url(self, logo_file_id: str, size: int | None = None) -> str:
        mc = self.minio_client
        object_name = self.get_club_logo_object_name(logo_file_id, size)
        return urlunsplit(
            mc._base_url.build(
                method="GET",
                region=mc._get_region(self.bucket),
                bucket_name=self.bucket,
                object_name=object_name,
            )
        )

    def put_club_logo(self, logo_file_id: str, size: int | None, data: bytes, content_type: str) -> None:
        object_name = self.get_club_logo_object_name(logo_file_id, size)
        self.minio_client.put_object(
            bucket_name=self.bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )


logos_repo = LogosRepo()
