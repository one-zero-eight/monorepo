from pydantic import Field, SecretStr

from src.common_config import ServiceSettingsBase, default_postgres_url


class TimerSettings(ServiceSettingsBase):
    db_url: SecretStr = Field(
        default_factory=lambda: default_postgres_url(driver="asyncpg", database="timer"),
        examples=[
            "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/timer",
            "postgresql+asyncpg://postgres:postgres@postgres:5432/timer",
        ],
    )
    "PostgreSQL database connection URL"
