# Backend Python Engineering — Team Standards

> Load this file as agent context when working on `backend/` code.

## Team Scope

You own **all backend Python code** in `backend/app/` and `backend/tests/`.

**Your files:**
- `backend/app/api/` — Route handlers (REST + WebSocket)
- `backend/app/core/config.py` — Application settings
- `backend/app/core/database.py` — SQLAlchemy engine, session factory
- `backend/app/models/` — ORM models (except `User` schema changes — coordinate with Auth team)
- `backend/app/schemas/` — Pydantic request/response schemas
- `backend/app/providers/` — External data source adapters (Finnhub, Alpha Vantage, yfinance)
- `backend/app/services/` — Business logic (scheduler, WebSocket manager, chat, notifications)
- `backend/alembic/` — Database migrations
- `backend/requirements.txt` — Python dependencies

**Not your files (coordinate with respective teams):**
- `backend/app/core/auth.py` → Auth/Security team
- `backend/app/models/models.py` (User table columns) → Auth/Security team
- `backend/tests/` → Shared with Test Engineering (you write unit tests, they own integration/E2E)
- `deploy/` → DevOps team
- `frontend/` → Frontend team

---

## Coding Standards

### Python Style
- **Python 3.11+** — use modern syntax: `str | None`, `list[str]`, match statements
- **Formatter**: `black` (line length 100)
- **Linter**: `ruff` (replaces flake8 + isort + pyflakes)
- **Type checker**: `mypy --strict` on all new code
- **Imports**: stdlib → third-party → local, separated by blank lines (ruff handles this)

### FastAPI Conventions
```python
# Route handler pattern — always use dependency injection
@router.get("/resource", response_model=list[ResourceResponse])
async def list_resources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResourceResponse]:
    ...
```

- Every endpoint that touches user data **must** use `Depends(get_current_user)`
- Return Pydantic `response_model` — never return raw dicts from endpoints
- Use proper HTTP status codes: 201 (created), 204 (deleted), 409 (conflict), 422 (validation)
- Path parameters for resource IDs: `/resource/{resource_id}`
- Query parameters for filtering: `?limit=50&category=tech`

### Database & ORM
```python
# Model pattern — use SQLAlchemy 2.0 Mapped types
class NewModel(Base):
    __tablename__ = "new_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- **Always** use timezone-aware datetimes: `DateTime(timezone=True)`
- **Always** add `index=True` on foreign key columns and frequently queried fields
- **Always** add `created_at` with `server_default=func.now()` on every table
- **Never** use `Base.metadata.create_all()` in production — use Alembic migrations
- Use `select()` + `await db.execute()` — never use legacy `db.query()` syntax
- Use `on_conflict_do_nothing()` for idempotent upserts (see news dedup pattern)

### Alembic Migrations (NEW — Critical for team development)
```bash
# Generate migration from model changes
cd backend
alembic revision --autogenerate -m "add_foo_table"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

- Every model change **must** have a corresponding Alembic migration
- Migration messages: `add_<table>`, `alter_<table>_add_<column>`, `drop_<table>`
- Test migrations: `upgrade head` then `downgrade base` then `upgrade head` again
- Never edit a migration that has been merged to `main`

### Pydantic Schemas
```python
# Request schema — only fields the client sends
class ResourceCreate(BaseModel):
    name: str
    value: float
    category: str = "default"

# Response schema — what the API returns
class ResourceResponse(BaseModel):
    id: int
    name: str
    value: float
    created_at: datetime

    model_config = {"from_attributes": True}
```

- Request schemas: `*Create`, `*Update` (partial fields with `Optional`)
- Response schemas: `*Response` with `from_attributes = True`
- Never expose internal fields (e.g., `user_id` in responses unless needed)

### Provider Pattern
```python
# All external data sources go through the provider abstraction
class NewProvider(BaseProvider):
    """Implement the abstract interface, never call external APIs directly from routes."""

    async def fetch_data(self, params: dict) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.base_url, params=params, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
```

- All external API calls go through `providers/` — never call httpx directly from routes
- Set explicit `timeout=10.0` on all HTTP calls
- Handle provider failures gracefully — log + return empty, don't crash the scheduler
- Use the factory pattern (`providers/factory.py`) for swappable implementations

### Error Handling
```python
# Use HTTPException for client-facing errors
raise HTTPException(status_code=404, detail="Resource not found")

# Use logging for internal errors — never expose stack traces to clients
import logging
logger = logging.getLogger(__name__)

try:
    result = await provider.fetch_data()
except Exception:
    logger.exception("Provider fetch failed")
    return []  # Graceful degradation
```

- Client errors (4xx): `HTTPException` with clear `detail` message
- Server errors (5xx): Log with `logger.exception()`, return safe fallback
- Never return raw exception messages to clients
- Use structured logging: `logger.info("event", extra={"symbol": symbol, "user_id": uid})`

### WebSocket
- All broadcast messages follow: `{"type": "<type>", "data": {...}}`
- Valid types: `quotes`, `news`, `alert`, `ipo_update`
- New message types must be documented and coordinated with Frontend team
- WebSocket connections are unauthenticated (broadcast model) — sensitive data must NOT go through WS

### Blocking I/O in Async Code
```python
# When calling synchronous/blocking libraries (e.g., yfinance), wrap in run_in_executor
import asyncio

hist = await asyncio.get_event_loop().run_in_executor(
    None, lambda: yf.Ticker(symbol).history(period="1d", interval="5m")
)
```

- **Never** call blocking I/O directly in async handlers — it blocks the event loop for all users
- Use `run_in_executor(None, fn)` to run blocking code in a thread pool
- Prefer async libraries when available (`httpx` over `requests`, `asyncpg` over `psycopg2`)

### JSON Serialization for WebSocket
```python
# The codebase uses a custom _DatetimeEncoder for WebSocket payloads
# All datetimes are serialized to ISO 8601 strings automatically
class _DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

# Used by ws_manager.broadcast() — you don't call it directly
# But if adding new data types to WS payloads, ensure they're JSON-serializable
```

### PostgreSQL-Specific Patterns
```python
# on_conflict_do_nothing requires PostgreSQL dialect import
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(NewsArticle).values(**data).on_conflict_do_nothing(index_elements=["external_id"])

# CAVEAT: This does NOT work in SQLite (used in tests). For test compatibility,
# either mock the upsert or use a try/except IntegrityError pattern in tests.
```

### Adding a New Data Provider (Step-by-Step)
1. Create `backend/app/providers/new_provider.py` implementing the base interface
2. Register it in `backend/app/providers/factory.py` with a config key
3. Add config key to `backend/app/core/config.py` (e.g., `news_provider: str = "finnhub"`)
4. Add API key to `.env.example` if needed
5. Write tests in `backend/tests/test_providers.py` with mocked HTTP responses
6. Update `docs/` with provider setup instructions

### Performance Rules for Scale
- **Batch database operations** — use `insert().values([...])` instead of N individual inserts
- **Use Redis cache** for hot data (quotes: 30s TTL, news list: 60s TTL)
- **Connection pooling** — configure SQLAlchemy pool: `pool_size=20, max_overflow=10`
- **Async everywhere** — never use `requests` library, always `httpx` async
- **Avoid N+1 queries** — use `.options(joinedload(...))` or batch selects

---

## Scaling TODO

### Phase 1: Foundation (10K DAU)
- [ ] Switch from `metadata.create_all()` to Alembic migrations exclusively
- [ ] Add Redis cache layer for ticker quotes (30s TTL) and news feed (60s TTL)
- [ ] Configure SQLAlchemy connection pool: `pool_size=20, max_overflow=10, pool_recycle=3600`
- [ ] Add `/health` endpoint (returns 200) and `/ready` endpoint (checks DB + Redis connectivity)
- [ ] Add structured logging with `structlog` (JSON output for CloudWatch/ELK)
- [ ] Add request ID middleware for distributed tracing correlation
- [ ] Sanitize all yfinance float outputs (NaN/Inf → null) — partially done, needs comprehensive fix
- [ ] Add pagination to `/api/news` and `/api/ipos` endpoints (cursor-based, not offset)
- [ ] Create `Makefile` with common dev commands: `make dev`, `make test`, `make lint`, `make migrate`

### Phase 2: Scale (100K DAU)
- [ ] Implement Redis pub/sub for WebSocket broadcast (multi-instance support)
- [ ] Add database read replicas — route GET queries to replica
- [ ] Implement API versioning: `/api/v1/` prefix, deprecation headers
- [ ] Add background task queue (Celery or arq) for email/PagerDuty notifications
- [ ] Implement rate limiting middleware (token bucket, 100 req/min/user default)
- [ ] Add OpenTelemetry instrumentation for all endpoints
- [ ] Implement graceful shutdown: drain WebSocket connections, finish in-flight requests
- [ ] Add circuit breaker pattern for Finnhub/Alpha Vantage calls

### Phase 3: Global (1M DAU)
- [ ] Event-driven architecture: price updates via message queue (SQS/Pub-Sub)
- [ ] CQRS: separate read/write models for high-traffic queries
- [ ] Database partitioning: partition `user_watchlist` and `price_alerts` by user_id range
- [ ] Archive old news articles to cold storage (S3/GCS) after 90 days
- [ ] Implement tenant-aware caching for multi-market support
- [ ] Add GraphQL or gRPC option for power-user/mobile clients
- [ ] WebSocket clustering with sticky sessions or Redis Streams

---

## Local Development

```bash
# Start dependencies
docker compose up db -d

# Install deps
cd backend
pip install -r requirements.txt

# Run with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v

# Lint + format
ruff check . --fix
black .
mypy app/ --strict
```

---

## PR Checklist

- [ ] All new endpoints have Pydantic request/response schemas
- [ ] All new endpoints have `Depends(get_current_user)` where user data is involved
- [ ] All new models have Alembic migration
- [ ] All new provider calls have timeout + error handling
- [ ] `pytest tests/ -v` passes with no failures
- [ ] No new `# type: ignore` without explanation
- [ ] WebSocket message type changes coordinated with Frontend team
- [ ] No hardcoded secrets or API keys
