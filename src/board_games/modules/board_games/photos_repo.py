__all__ = ["photos_repo"]

import io

from minio import Minio

from src.board_games.config import settings
from src.common_minio import MinioStore


class PhotosRepo:
    def __init__(self) -> None:
        self._minio_store: MinioStore | None = None

    def post_init(self, minio_store: MinioStore) -> None:
        self._minio_store = minio_store

    @property
    def minio_client(self) -> Minio:
        if self._minio_store is None:  # pragma: no cover
            raise RuntimeError("PhotosRepo.post_init was not called from app lifespan")
        return self._minio_store.client

    @property
    def bucket(self) -> str:
        if self._minio_store is None:  # pragma: no cover
            raise RuntimeError("PhotosRepo.post_init was not called from app lifespan")
        return self._minio_store.bucket_name

    def get_object_name(self, photo_file_id: str, size: int | None = None) -> str:
        size_postfix = f"-{size}" if size else ""
        return f"{settings.minio.board_game_photos_prefix}{photo_file_id}{size_postfix}"

    def get_url(self, photo_file_id: str, size: int | None = None) -> str:
        object_name = self.get_object_name(photo_file_id, size)
        return self.minio_client.presigned_get_object(self.bucket, object_name)

    def put(self, photo_file_id: str, size: int | None, data: bytes, content_type: str) -> None:
        self.minio_client.put_object(
            bucket_name=self.bucket,
            object_name=self.get_object_name(photo_file_id, size),
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )


photos_repo = PhotosRepo()
