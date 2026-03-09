# Backend Team — Phase 1 Completion Sprint

**Sprint Duration:** 2 weeks
**Team Lead:** Backend Python Team
**Reference:** [backend-python.md](../backend-python.md) for coding standards

---

## Sprint Goal

Eliminate the two biggest scaling bottlenecks: **every request hitting PostgreSQL** (add Redis cache) and **untuned connection pool** (configure for concurrent load). These are the P0 blockers preventing us from handling 10K DAU.

---

## Tasks

### Task 1: Redis Cache for Quotes and News (P0) — 3 days

**Why:** At current polling rates (quotes every 30s, news every 60s), every dashboard load hits the DB directly. At 10K DAU with 3-5 page loads per session, that's 30K-50K unnecessary DB queries per day.

**Implementation:**

1. Add `redis[hiredis]` to requirements.txt
2. Create `app/core/cache.py`:
   ```python
   # Use the same pattern as database.py — module-level singleton
   import redis.asyncio as redis
   from app.core.config import settings

   redis_client: redis.Redis | None = None

   async def get_redis() -> redis.Redis:
       global redis_client
       if redis_client is None:
           redis_client = redis.from_url(
               settings.redis_url,
               encoding="utf-8",
               decode_responses=True,
           )
       return redis_client

   async def close_redis():
       global redis_client
       if redis_client:
           await redis_client.close()
           redis_client = None
   ```

3. Add to `app/core/config.py`:
   ```python
   redis_url: str = "redis://localhost:6379/0"
   cache_quotes_ttl: int = 30   # seconds
   cache_news_ttl: int = 60     # seconds
   ```

4. Add cache layer in routes — **cache-aside pattern**:
   ```python
   # In GET /tickers or GET /watchlist — cache the full response
   cache_key = f"quotes:{user_id}"
   cached = await redis.get(cache_key)
   if cached:
       return json.loads(cached)
   # ... fetch from DB ...
   await redis.setex(cache_key, settings.cache_quotes_ttl, json.dumps(result))
   ```

5. Invalidate cache in scheduler after `poll_quotes()` broadcasts:
   ```python
   # After updating DB, delete stale quote caches
   keys = await redis.keys("quotes:*")
   if keys:
       await redis.delete(*keys)
   ```

6. Hook into lifespan in `main.py`:
   ```python
   from app.core.cache import close_redis
   # In lifespan shutdown:
   await close_redis()
   ```

**Testing:**
- Use `fakeredis` for unit tests (add to requirements-dev.txt)
- Integration test: verify cache hit returns same data as DB fetch
- Integration test: verify cache invalidation after poll

**Acceptance Criteria:**
- [ ] GET /tickers returns cached data within TTL
- [ ] Scheduler invalidates cache after each poll cycle
- [ ] Cache miss falls through to DB transparently
- [ ] fakeredis tests pass in CI (no real Redis needed)

---

### Task 2: DB Connection Pool Tuning (P0) — 1 day

**Why:** Default asyncpg pool is pool_size=5. At 10K DAU with bursty traffic, connections will queue and timeout.

**Implementation in `app/core/database.py`:**

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=20,          # was default 5
    max_overflow=10,       # burst capacity
    pool_timeout=30,       # seconds to wait for connection
    pool_recycle=1800,     # recycle connections every 30 min
    pool_pre_ping=True,    # detect stale connections
)
```

Add to `app/core/config.py`:
```python
db_pool_size: int = 20
db_max_overflow: int = 10
db_pool_timeout: int = 30
db_pool_recycle: int = 1800
```

**Testing:**
- Load test locally with k6: 50 concurrent users for 60s
- Monitor with `SELECT count(*) FROM pg_stat_activity` during test
- Verify no "too many connections" errors

**Acceptance Criteria:**
- [ ] Pool configured from settings (not hardcoded)
- [ ] pool_pre_ping enabled
- [ ] No connection timeout under 50 concurrent local users

---

### Task 3: Structured Logging with structlog (P1) — 2 days

**Why:** Current `logging.basicConfig` outputs plain text. In production with multiple containers, we need JSON logs with request context for debugging.

**Implementation:**

1. Add `structlog` to requirements.txt
2. Create `app/core/logging.py`:
   ```python
   import structlog

   def setup_logging(log_level: str = "INFO"):
       structlog.configure(
           processors=[
               structlog.contextvars.merge_contextvars,
               structlog.processors.add_log_level,
               structlog.processors.TimeStamper(fmt="iso"),
               structlog.processors.JSONRenderer(),
           ],
           logger_factory=structlog.PrintLoggerFactory(),
       )
   ```

3. Replace `logger = logging.getLogger(__name__)` with `logger = structlog.get_logger()` in all modules
4. Add request context middleware:
   ```python
   @app.middleware("http")
   async def add_request_context(request, call_next):
       request_id = request.headers.get("X-Request-ID", str(uuid4()))
       structlog.contextvars.clear_contextvars()
       structlog.contextvars.bind_contextvars(request_id=request_id)
       response = await call_next(request)
       response.headers["X-Request-ID"] = request_id
       return response
   ```

**Acceptance Criteria:**
- [ ] All log output is JSON in production
- [ ] Every log line includes request_id
- [ ] Existing log.info/log.exception calls still work

---

### Task 4: Cursor-Based Pagination (P1) — 2 days

**Why:** `/news` and `/ipos` return all rows. At scale, this becomes unbounded.

**Implementation:**
- Use `created_at` + `id` as cursor (both are indexed, both are monotonic)
- Query pattern: `WHERE (created_at, id) < (:cursor_ts, :cursor_id) ORDER BY created_at DESC, id DESC LIMIT :limit`
- Return cursor in response: `{ "items": [...], "next_cursor": "2026-03-09T12:00:00Z_42" }`
- Default limit: 50, max limit: 200

**Acceptance Criteria:**
- [ ] GET /news?limit=20&cursor=... returns paginated results
- [ ] GET /ipos?limit=20&cursor=... returns paginated results
- [ ] Existing clients work without cursor (returns first page)

---

## Coordination

- **With DevOps:** Need Redis available in staging by Day 3. Use `redis://localhost:6379` for local dev. Coordinate `REDIS_URL` env var naming.
- **With Test:** Provide `fakeredis` fixture in conftest.py so test team can write cache tests.
- **With Auth:** Rate limiting will need Redis too. Use the same `get_redis()` singleton — don't create a separate connection.

---

## Out of Scope This Sprint

- Redis pub/sub for WebSocket (Phase 2)
- Read replicas (Phase 2)
- API versioning (Phase 2)
- Circuit breaker pattern (defer to Phase 2 — current try/catch is sufficient for 10K DAU)

---

*Questions? Tag @backend-lead in the PR or post in #backend-team channel.*
