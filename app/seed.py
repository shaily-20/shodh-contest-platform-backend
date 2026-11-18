from app.db import engine
from app.models import Base


async def seed() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed())
