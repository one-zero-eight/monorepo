__all__ = ["MinioStore", "setup_minio"]

import os

from minio import Minio
from minio.error import MinioException
from urllib3.exceptions import HTTPError

from src.common_config import MinioSettings
from src.logging_ import logger


class MinioStore:
    def __init__(self, client: Minio, bucket_name: str) -> None:
        self._client = client
        self.original_bucket_name = bucket_name
        self.current_bucket_name = bucket_name
        self.ensure_bucket()

    @property
    def client(self) -> Minio:
        return self._client

    @property
    def bucket_name(self) -> str:
        return self.current_bucket_name

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self.bucket_name):
            self._client.make_bucket(self.bucket_name)

    def rotate_bucket(self, bucket_name: str) -> None:
        """
        Switch to a different bucket. Used for testing.
        """
        if "PYTEST_CURRENT_TEST" not in os.environ:
            raise RuntimeError("Cannot rotate bucket outside of a test")
        self.current_bucket_name = bucket_name
        self.ensure_bucket()

    def clear_bucket(self) -> None:
        """Remove every object in the current bucket (no-op if the bucket does not exist)."""
        if "PYTEST_CURRENT_TEST" not in os.environ:
            raise RuntimeError("Cannot clear bucket outside of a test")
        bucket = self.bucket_name
        if not self._client.bucket_exists(bucket):
            return
        for obj in self._client.list_objects(bucket, recursive=True):
            if obj.object_name:
                self._client.remove_object(bucket, obj.object_name)


def setup_minio(minio: MinioSettings) -> MinioStore:
    client = Minio(
        endpoint=minio.endpoint,
        secure=minio.secure,
        region=minio.region,
        access_key=minio.access_key,
        secret_key=minio.secret_key.get_secret_value(),
    )

    try:
        n = len(client.list_buckets())
        logger.info(f"Connected to MinIO ({n} buckets)")
    except (MinioException, HTTPError, OSError) as e:  # pragma: no cover
        logger.critical(f"Could not connect to MinIO: {e}")

    return MinioStore(client, minio.bucket)
