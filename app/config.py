from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://shodh:shodh@postgres:5432/shodh"
    runner_mode: str = "double"
    worker_id: str = "worker"
    max_attempt_retries: int = 3
    lease_seconds: int = 300
    runner_timeout_seconds: int = 2
    runner_memory_bytes: int = 64 * 1024 * 1024

    class Config:
        env_file = ".env"


settings = Settings()
