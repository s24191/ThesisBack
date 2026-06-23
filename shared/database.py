import os

from dotenv import load_dotenv
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

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
