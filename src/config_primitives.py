from enum import StrEnum

from src.pydantic_base import BaseSchema


class Environment(StrEnum):
    DEVELOPMENT = "development"
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
