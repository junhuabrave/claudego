# Phase 1 — Foundation Tasks

> Prioritized task list for team review. Pick tasks top-down by priority.
> Reference: `.claude/teams/test-engineering.md` and `SCALING_ROADMAP.md`

## Task List

| # | Task | Priority | Area | Status |
|---|------|----------|------|--------|
| 1 | Set up GitHub Actions CI pipeline (lint + test + build) | P0 | DevOps | Pending |
| 2 | Add cursor-based pagination to `/api/news` and `/api/ipos` | P1 | Backend | Pending |
| 3 | Add structured logging with structlog (JSON output) | P1 | Backend | Pending |
| 4 | Add request ID middleware for tracing | P1 | Backend | Pending |
| 5 | Add rate limiting middleware (100 req/min) | P0 | Security | Pending |
| 6 | Add `/ready` health check endpoint | P0 | Backend | Pending |
| 7 | Optimize Dockerfiles (multi-stage, non-root, .dockerignore) | P0 | DevOps | Pending |
| 8 | Add frontend ErrorBoundary component | P1 | Frontend | Pending |
| 9 | Add input validation regex for ticker symbols | P1 | Security | Pending |
| 10 | Fix pre-existing test_auth.py failures (Google OAuth mock) | P1 | Testing | Done |

---

## Task Details

### 1. GitHub Actions CI Pipeline
- Run `ruff` (backend lint) + `eslint` (frontend lint)
- Run `pytest` (backend tests) + `npm test` (frontend tests)
- Build Docker images to verify Dockerfiles
- Trigger on PR and push to `main`

### 2. Cursor-Based Pagination
- `/api/news` and `/api/ipos` currently return unbounded results
- Add `?cursor=<id>&limit=20` query params
- Return `next_cursor` in response for client-side pagination

### 3. Structured Logging (structlog)
- Replace `print()` / basic `logging` with `structlog`
- JSON output format for production, colored console for dev
- Include request context (user ID, session ID, endpoint)

### 4. Request ID Middleware
- Generate UUID per request via middleware
- Attach to all log entries and return in `X-Request-ID` response header
- Enables end-to-end request tracing

### 5. Rate Limiting Middleware
- Add `slowapi` or custom middleware
- 100 requests/min per session ID / IP
- Return `429 Too Many Requests` with `Retry-After` header

### 6. `/ready` Health Check Endpoint
- `GET /ready` returns `200` when DB connection is healthy
- Used by Docker health checks and load balancers
- Separate from existing `/health` (if any) — checks actual dependencies

### 7. Optimize Dockerfiles
- Multi-stage builds to reduce image size
- Run as non-root user
- Add `.dockerignore` files to exclude `node_modules`, `__pycache__`, `.git`
- Pin base image versions

### 8. Frontend ErrorBoundary
- React ErrorBoundary component wrapping the app
- Shows user-friendly error UI instead of white screen
- Logs error details for debugging

### 9. Ticker Symbol Validation
- Validate ticker input with regex: `^[A-Z]{1,5}$`
- Reject invalid symbols at API boundary (422 response)
- Add frontend input validation to match

### 10. Fix test_auth.py Failures ✓ Done
- Patched `settings.google_client_id` alongside `verify_oauth2_token` mock so tests bypass the 503 guard
- `--ignore=tests/test_auth.py` removed from CI; all auth tests now run
