"""Content creation service configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Externalized configuration loaded from environment variables."""

    APP_NAME: str = "content_creation"
    APP_ENV: str = "development"
    APP_PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+psycopg://user:password@localhost:5432/content_creation"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_SECRET_NAME: str = "content_creation/secrets"

    # Pipeline
    PIPELINE_BASE_URL: str = "http://localhost:8001"
    PIPELINE_TIMEOUT: int = 30
    PIPELINE_MAX_RETRIES: int = 3
    PIPELINE_BACKOFF_FACTOR: float = 2.0

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_AUDIENCE: str = "content_creation"
    JWT_SECRET_NAME: str = "content_creation/jwt-secret"
    JWT_SECRET_KEY: str = "dev-secret-key"

    # Content validation
    MIN_CONTENT_LENGTH: int = 10
    MAX_CONTENT_LENGTH: int = 50000

    # Logging
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "content_creation"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
