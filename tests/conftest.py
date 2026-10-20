import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

import models  # noqa: F401
from bootstrap import create_app
from db.base import AbsBase
from db.session import get_async_session


@pytest.fixture(scope="session")
def postgres_container():
    """Один PostgreSQL на всю сессию. Его используют только тесты, которым нужна база."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def postgres_url(postgres_container):
    url = postgres_container.get_connection_url()
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session")
def database_schema(postgres_url):
    """Создаёт таблицы один раз. Повторный create_all на тех же ENUM не нужен."""

    async def create_schema() -> None:
        engine = create_async_engine(postgres_url, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(AbsBase.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_schema())


@pytest_asyncio.fixture
async def engine(postgres_url, database_schema):
    engine = create_async_engine(postgres_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    """Фабрика сессий. После теста таблицы пустые."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    async with engine.begin() as conn:
        for table in reversed(AbsBase.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def session(db):
    async with db() as opened:
        yield opened


@pytest_asyncio.fixture
async def client(session):
    """HTTP-клиент приложения с сессией теста вместо пула из настроек."""
    app = create_app()

    async def override_get_async_session():
        yield session

    app.dependency_overrides[get_async_session] = override_get_async_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
