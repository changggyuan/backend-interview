from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./app.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM Model 共用的 Declarative Base。"""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """提供 FastAPI 依賴注入使用的非同步資料庫 Session。"""

    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """啟動時建立尚未存在的資料表。"""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
