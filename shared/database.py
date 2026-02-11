import os
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shared.seed.wine_seed import seed_wines_from_csvs

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://wine_user:wine_password@localhost:5432/wine_db")

engine = create_async_engine(DATABASE_URL, echo=True)

async_session_maker = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    import shared.models # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def seed_db_from_csv() -> None:
    async with async_session_maker() as session:
        await seed_wines_from_csvs(session)