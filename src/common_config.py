from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr

from src.common_pydantic import BaseSchema
from src.logging_ import logger


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class ServiceSettingsBase(BaseSchema):
    """Common application settings for all services."""

    environment: Environment = Environment.DEVELOPMENT
    "App environment flag"
    app_root_path: str = ""
    'Prefix for the API path (e.g. "/api/v0")'
    cors_allow_origin_regex: str = ".*"
    """
    Allowed origins for CORS: from which domains requests to the API are allowed.
    Specify as a regex: `https://.*.innohassle.ru`
    """


def is_running_in_docker() -> bool:  # pragma: no cover
    def _check() -> bool:
        # Common in many Docker containers
        if Path("/.dockerenv").exists():
            return True

        # Works on many Linux hosts/containers
        cgroup_paths = [
            Path("/proc/self/cgroup"),
            Path("/proc/1/cgroup"),
        ]

        markers = ("docker", "containerd", "kubepods", "podman", "lxc")

        for path in cgroup_paths:
            try:
                content = path.read_text()
            except OSError:
                continue

            if any(marker in content for marker in markers):
                return True

        return False

    result = _check()

    if result:
        logger.info("Running in Docker, using MongoDB at mongodb:27017, MinIO at minio:9000")
    else:
        logger.info("Running locally, using MongoDB at 127.0.0.1:27017, MinIO at 127.0.0.1:9000")

    return result


def default_mongo_uri() -> SecretStr:
    in_docker = is_running_in_docker()
    if in_docker:
        return SecretStr("mongodb://onezeroeight:herewethinkbig@mongodb:27017/?authSource=admin")
    else:
        return SecretStr("mongodb://onezeroeight:herewethinkbig@127.0.0.1:27017/?authSource=admin")


def default_minio_endpoint() -> str:
    in_docker = is_running_in_docker()
    if in_docker:
        return "minio:9000"
    else:
        return "127.0.0.1:9000"


class MongoDatabaseSettings(BaseSchema):
    uri: SecretStr = Field(
        default_factory=default_mongo_uri,
        examples=[
            "mongodb://onezeroeight:herewethinkbig@127.0.0.1:27017/?authSource=admin",
            "mongodb://onezeroeight:herewethinkbig@mongodb:27017/?authSource=admin",
        ],
    )
    "MongoDB database settings, if you do not specify database name in the uri, it will use the service name (f.e. 'clubs')"


class MinioSettings(BaseSchema):
    endpoint: str = Field(
        default_factory=default_minio_endpoint,
        examples=["127.0.0.1:9000", "minio:9000"],
    )
    "URL of the target service."
    secure: bool = False
    "Use https connection to the service."
    region: str | None = None
    "Region of the service."
    bucket: str = "clubs"
    "Name of the bucket in the service."
    access_key: str = "onezeroeight"
    "Access key (user ID) of a user account in the service."
    secret_key: SecretStr = SecretStr("herewethinkbig")
    "Secret key (password) for the user account."
    club_logos_prefix: str = "logos/"
