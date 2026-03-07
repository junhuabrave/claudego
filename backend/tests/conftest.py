"""Shared test fixtures.

Uses an in-memory SQLite database so tests run without PostgreSQL.
A lightweight test FastAPI app (no lifespan/scheduler) wraps the real routers.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import router as auth_router
from app.api.routes import router as api_router
from app.core.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    TestSession = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session


# ---------------------------------------------------------------------------
# Test app + HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """AsyncClient against a minimal test app (no scheduler, no lifespan)."""

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(auth_router, prefix="/api")
    test_app.include_router(api_router, prefix="/api")

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def anon_headers(session_id: str) -> dict:
    return {"X-Session-ID": session_id}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
