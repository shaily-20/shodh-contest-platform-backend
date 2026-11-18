from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://shodh:shodh@postgres:5432/shodh"
    worker_id: str = "worker"
    runner_timeout_seconds: int = 2
    runner_memory_bytes: int = 64 * 1024 * 1024
    runner_image: str = "python:3.12-alpine"
    jwt_secret: str = "dev-only-change-this-secret-before-deployment"
    organizer_registration_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
