"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # Server
    server_port: int = 8080
    server_env: str = "development"
    public_url: str = "http://localhost"
    cookie_secure: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://paca:paca@localhost:5432/paca"

    # Redis / Valkey
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    jwt_refresh_session_ttl_hours: int = 24

    # Admin
    admin_username: str = "admin"
    admin_password: str = "changeme123"

    # Storage
    storage_provider: str = "minio"  # "minio" | "s3"
    storage_endpoint: str = "localhost:9000"
    storage_public_url: str = "http://localhost/storage"
    storage_region: str = "us-east-1"
    storage_bucket: str = "paca"
    storage_access_key_id: str = "minioadmin"
    storage_secret_access_key: str = "minioadmin"
    storage_use_ssl: bool = False

    # Security
    encryption_key: str = ""
    agent_api_key: str = ""

    # Cache TTLs (seconds)
    cache_project_ttl: int = 300
    cache_config_ttl: int = 600
    cache_sprint_ttl: int = 120

    # AI Agent
    ai_agent_url: str = "http://ai-agent:8080"

    @property
    def sync_database_url(self) -> str:
        """Return synchronous database URL for Alembic migrations."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
