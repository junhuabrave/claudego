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
from app.core.auth import create_access_token
from app.core.database import Base, get_db
from app.models.models import User

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


@pytest_asyncio.fixture
async def google_auth_headers(db_session) -> dict:
    """
    Creates a Google-authenticated User in the test DB and returns the
    corresponding Bearer auth headers.

    Use this fixture for Tier 2 endpoints that require require_google_user
    (e.g. reminders). Use anon_headers() for Tier 1 endpoints.
    """
    user = User(google_id="test-google-id-fixture", email="fixture@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user.id)
    return auth_headers(token)
