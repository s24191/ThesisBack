import asyncio

from shared.database import engine
from sqlmodel import SQLModel

import shared.models  # noqa: F401


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def main():
    await init_db()


if __name__ == "__main__":
    asyncio.run(main())