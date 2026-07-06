import os

# Override BEFORE any app imports — pydantic-settings reads env vars at Settings() init time
os.environ["POSTGRES_URL"] = "postgresql+asyncpg://interview:interview@localhost:5432/interview_bot_test"
os.environ["MONGO_DB"] = "interview_bot_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_ROOT = Path(__file__).parent.parent
_TEST_PG_URL = "postgresql+asyncpg://interview:interview@localhost:5432/interview_bot_test"
_TEST_PG_ADMIN = "postgresql://interview:interview@localhost:5432/postgres"


# ---------------------------------------------------------------------------
# PostgreSQL: test DB lifecycle (once per session)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def pg_test_engine():
    admin = await asyncpg.connect(_TEST_PG_ADMIN)
    await admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = 'interview_bot_test' AND pid <> pg_backend_pid()"
    )
    await admin.execute("DROP DATABASE IF EXISTS interview_bot_test")
    await admin.execute("CREATE DATABASE interview_bot_test")
    await admin.close()

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_ROOT,
        check=True,
        env={**os.environ},
    )

    engine = create_async_engine(_TEST_PG_URL, echo=False)
    yield engine
    await engine.dispose()

    admin = await asyncpg.connect(_TEST_PG_ADMIN)
    await admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = 'interview_bot_test' AND pid <> pg_backend_pid()"
    )
    await admin.execute("DROP DATABASE IF EXISTS interview_bot_test")
    await admin.close()


# ---------------------------------------------------------------------------
# PostgreSQL: SAVEPOINT-based session (per test, for service-level tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session(pg_test_engine):
    """
    Wraps each test in a SAVEPOINT. Every session.commit() in app code releases the
    SAVEPOINT; the event listener immediately creates a new one. The outer transaction
    is rolled back at teardown, leaving the DB unchanged.
    """
    conn = await pg_test_engine.connect()
    await conn.begin()
    await conn.begin_nested()

    session = AsyncSession(bind=conn, expire_on_commit=False)

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _restart_savepoint(sync_sess, txn):
        if not conn.closed and not conn.sync_connection.in_nested_transaction():
            conn.sync_connection.begin_nested()

    yield session

    await session.close()
    await conn.rollback()
    await conn.close()


# ---------------------------------------------------------------------------
# MongoDB: test database (dropped after each test)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def mongo_test_client():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    yield client
    client.close()


@pytest_asyncio.fixture
async def mongo_clean(mongo_test_client):
    yield mongo_test_client["interview_bot_test"]
    await mongo_test_client.drop_database("interview_bot_test")


# ---------------------------------------------------------------------------
# Redis: DB index 1, flushed after each test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def redis_test():
    from redis.asyncio import from_url
    client = from_url("redis://localhost:6379/1", decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def redis_clean(redis_test):
    yield redis_test
    await redis_test.flushdb()


# ---------------------------------------------------------------------------
# HTTP client for API integration tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(pg_test_engine, redis_clean, mongo_clean):
    from db.postgres import get_db
    from main import app

    test_factory = async_sessionmaker(pg_test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()

    # Truncate all data after each API test
    async with pg_test_engine.connect() as conn:
        await conn.execute(text("TRUNCATE scores, sessions, users CASCADE"))
        await conn.commit()
