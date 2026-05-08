from enum import StrEnum

from pydantic import Field, SecretStr

from src.common_pydantic import BaseSchema


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


class MongoDatabaseSettings(BaseSchema):
    uri: SecretStr = Field(
        default=SecretStr("mongodb://onezeroeight:herewethinkbig@127.0.0.1:27017/?authSource=admin"),
        examples=[
            "mongodb://onezeroeight:herewethinkbig@127.0.0.1:27017/?authSource=admin",
            "mongodb://onezeroeight:herewethinkbig@db:27017/?authSource=admin",
        ],
    )
    "MongoDB database settings, if you do not specify database name in the uri, it will use the service name (f.e. 'clubs')"
