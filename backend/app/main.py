"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.routes import router
from app.core.config import settings
from app.core.database import engine
from app.services.scheduler import poll_ipos, start_scheduler, stop_scheduler

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Schema is managed exclusively by Alembic migrations.
    # Run `alembic upgrade head` before starting the application in any environment.
    # Never use Base.metadata.create_all() in production — it cannot roll back
    # and silently skips columns that already exist.
    start_scheduler()
    await poll_ipos()  # seed DB immediately; scheduler runs hourly after this
    yield
    # Shutdown
    stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title="Financial Markets Monitor",
    description="Real-time global financial markets monitoring system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    """Liveness probe — returns 200 if the process is running."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """
    Readiness probe — returns 200 only when the app can serve traffic.
    Checks DB connectivity. Used by ECS health checks and load balancer
    target group health checks to gate traffic during deploys.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed — DB unreachable")
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}
