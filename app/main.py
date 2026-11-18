from fastapi import FastAPI
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.models import Base

app = FastAPI(
    title="Shodh Contest Platform API",
    version="0.1.0",
    description="Backend API for the Shodh coding contest platform.",
)


@app.on_event("startup")
async def initialize_database() -> None:
    # This keeps the starter deployable. Use Alembic migrations for production changes.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {"service": "shodh-contest-platform-backend", "status": "ok", "docs": "/docs"}


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "healthy"}
