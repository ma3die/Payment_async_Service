from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from config import settings

connect_args = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
}

engine: AsyncEngine = create_async_engine(
    settings.db.DATABASE_URL,
    future=True,
    echo=False,  # sql logs
    pool_size=10,  # Размер пула соединений
    max_overflow=20,  # Максимальное количество дополнительных соединений сверх пула
    poolclass=AsyncAdaptedQueuePool,  # Класс пула соединений
    pool_pre_ping=True,  # Предварительный пинг для проверки соединений
    connect_args=connect_args,
    pool_timeout=150,  # Таймаут ожидания свободного соединения в пуле
    pool_recycle=3600,  # Переподключение соединений каждые 3600 секунд (1 час)
)

async_session_maker = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Отдаёт сессию на время HTTP-запроса."""
    async with async_session_maker() as session:
        yield session
