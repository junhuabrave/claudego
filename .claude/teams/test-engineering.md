# Test Engineering — Team Standards

> Load this file as agent context when working on test infrastructure and quality assurance.

## Team Scope

You own **test infrastructure, E2E tests, load tests, and test quality standards** across the entire project.

**Your files:**
- `backend/tests/` — Backend test suite (shared ownership with Backend team)
- `backend/tests/conftest.py` — Shared test fixtures and utilities
- `frontend/src/__tests__/` — Frontend test suite (shared ownership with Frontend team)
- `tests/e2e/` — End-to-end Playwright tests (NEW — you create this)
- `tests/load/` — Load testing scripts with k6 or Locust (NEW — you create this)
- `tests/security/` — Security scanning configs (NEW — shared with Auth team)
- `.github/workflows/*test*` — CI test pipeline configs (shared with DevOps)

**Your responsibilities:**
- Define and enforce test coverage thresholds
- Build shared test fixtures and utilities
- Create and maintain E2E test suite
- Run load tests before major releases
- Review test quality in all PRs (all teams)
- Maintain CI test pipeline reliability

**Not your files:**
- Application source code (you don't write features, you test them)
- Deployment configs → DevOps team
- But you DO write test helpers, mocks, and fixtures that live alongside source

---

## Testing Standards

### Test Pyramid
```
        ╱╲
       ╱  ╲         E2E Tests (Playwright)
      ╱ 10% ╲       - Critical user flows only
     ╱────────╲      - Login → add ticker → see price → set alert
    ╱          ╲
   ╱  30%       ╲   Integration Tests (pytest + TestClient)
  ╱──────────────╲   - API endpoint tests with real DB (in-memory SQLite)
 ╱                ╲  - WebSocket connection tests
╱    60%           ╲ Unit Tests (pytest + Jest)
╱───────────────────╲ - Business logic, schemas, providers, components
```

- **Unit tests**: Fast, isolated, no I/O. Test one function/component at a time.
- **Integration tests**: Test API endpoints with database. Use in-memory SQLite.
- **E2E tests**: Test critical user flows in a real browser. Run against docker-compose stack.

### Backend Testing (pytest)

#### Test File Naming
```
backend/tests/
├── conftest.py              # Shared fixtures (db_engine, db_session, client, auth helpers)
├── test_auth.py             # Authentication flows
├── test_tickers.py          # Watchlist CRUD
├── test_alerts.py           # Price alerts CRUD + evaluation logic
├── test_news.py             # News feed endpoints (NEW)
├── test_ipos.py             # IPO calendar endpoints (NEW)
├── test_chat.py             # Chat command parsing (NEW)
├── test_scheduler.py        # Background job logic (NEW)
├── test_providers.py        # Provider adapters with mocked HTTP (NEW)
└── test_websocket.py        # WebSocket connection + broadcast (NEW)
```

- File naming: `test_<module>.py`
- Function naming: `test_<what>_<condition>_<expected>` (e.g., `test_create_alert_invalid_direction_returns_422`)
- Class naming (optional grouping): `class TestPriceAlerts:`

#### Fixture Pattern (conftest.py)
```python
# Current fixture pattern — maintain this style

@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite engine with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    """Async session for each test — auto-rolls back."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session

@pytest_asyncio.fixture
async def client(db_session):
    """Test client with DB dependency override."""
    app_copy = FastAPI()
    app_copy.include_router(router, prefix="/api")
    app_copy.include_router(auth_router, prefix="/api/auth")
    app_copy.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app_copy), base_url="http://test") as ac:
        yield ac
```

#### Auth Test Helpers
```python
# Anonymous user — sends X-Session-ID header
def anon_headers(session_id: str = "test-session-123") -> dict:
    return {"X-Session-ID": session_id}

# Authenticated user — sends Bearer token
def auth_headers(user_id: int) -> dict:
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=1)},
        "test-secret", algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}
```

#### Test Pattern
```python
@pytest.mark.asyncio
async def test_add_ticker_creates_watchlist_entry(client, db_session):
    """POST /api/tickers should create both Ticker and UserWatchlist rows."""
    resp = await client.post(
        "/api/tickers",
        json={"symbol": "AAPL", "name": "Apple Inc", "exchange": "NASDAQ"},
        headers=anon_headers(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["name"] == "Apple Inc"

    # Verify DB state
    result = await db_session.execute(
        select(UserWatchlist).where(UserWatchlist.symbol == "AAPL")
    )
    assert result.scalar_one_or_none() is not None
```

#### Mocking External Services
```python
# Mock Finnhub API calls — never hit real APIs in tests
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_poll_quotes_updates_prices(db_session):
    mock_provider = AsyncMock()
    mock_provider.fetch_quotes.return_value = [
        {"symbol": "AAPL", "price": 200.50, "change_percent": 2.3}
    ]
    with patch("app.providers.factory.get_quote_provider", return_value=mock_provider):
        await poll_quotes(db_session)

    ticker = await db_session.execute(select(Ticker).where(Ticker.symbol == "AAPL"))
    assert ticker.scalar_one().last_price == 200.50
```

### Frontend Testing (Jest + React Testing Library)

#### Test Pattern
```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WatchList from "../components/WatchList";

describe("WatchList", () => {
  const mockTickers = [
    { symbol: "AAPL", name: "Apple", last_price: 200, change_percent: 2.3 },
  ];

  it("renders ticker symbols", () => {
    render(<WatchList tickers={mockTickers} onRemove={jest.fn()} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });

  it("calls onRemove when delete button clicked", async () => {
    const onRemove = jest.fn();
    render(<WatchList tickers={mockTickers} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
  });

  it("shows empty state when no tickers", () => {
    render(<WatchList tickers={[]} onRemove={jest.fn()} />);
    expect(screen.getByText(/no tickers/i)).toBeInTheDocument();
  });
});
```

- **Test behavior, not implementation** — query by role/text, not by className/testId
- **Use `userEvent` over `fireEvent`** for realistic user interactions
- **Mock API calls** with `jest.mock("../services/api")`
- **Wrap with providers** when testing components that use context (AuthContext)

### E2E Testing (Playwright — NEW)

#### Setup
```
tests/e2e/
├── playwright.config.ts    # Config: baseURL, browsers, retries
├── fixtures/
│   └── auth.ts             # Login helper fixture
├── specs/
│   ├── login.spec.ts       # Google OAuth login flow
│   ├── watchlist.spec.ts   # Add/remove tickers via UI
│   ├── alerts.spec.ts      # Create/modify/delete price alerts
│   ├── news-feed.spec.ts   # News feed loads and updates
│   └── chat.spec.ts        # Chat commands work
└── global-setup.ts         # Start docker-compose before all tests
```

#### E2E Test Pattern
```typescript
import { test, expect } from "@playwright/test";

test.describe("Watchlist", () => {
  test("user can add a ticker via chat", async ({ page }) => {
    await page.goto("/");
    const chatInput = page.getByPlaceholder("Type a message");
    await chatInput.fill("add MSFT");
    await chatInput.press("Enter");

    // Wait for ticker to appear in watchlist
    await expect(page.getByText("MSFT")).toBeVisible({ timeout: 10000 });
  });
});
```

- E2E tests run against `docker-compose up` stack
- Only test **critical user flows** — don't duplicate unit test coverage
- Use `test.describe.serial()` for tests that depend on order
- Screenshots on failure: `screenshot: "only-on-failure"` in config

### Load Testing (k6 — NEW)

#### Setup
```
tests/load/
├── k6/
│   ├── smoke.js           # 5 users, 30 seconds — sanity check
│   ├── load.js            # 500 users, 5 minutes — target load
│   ├── stress.js          # 2000 users, 10 minutes — breaking point
│   ├── spike.js           # 0 → 1000 → 0 users — spike test
│   └── helpers/
│       └── auth.js        # Generate test session IDs / JWTs
└── results/               # k6 JSON output (gitignored)
```

#### Load Test Pattern (k6)
```javascript
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "1m", target: 100 },   // ramp up
    { duration: "3m", target: 500 },   // hold
    { duration: "1m", target: 0 },     // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"],   // 95th percentile < 500ms
    http_req_failed: ["rate<0.01"],     // <1% error rate
  },
};

export default function () {
  const headers = { "X-Session-ID": `load-test-${__VU}` };

  // GET tickers
  const tickersRes = http.get("http://localhost:8000/api/tickers", { headers });
  check(tickersRes, { "tickers 200": (r) => r.status === 200 });

  // GET news
  const newsRes = http.get("http://localhost:8000/api/news");
  check(newsRes, { "news 200": (r) => r.status === 200 });

  sleep(1);
}
```

#### Performance Targets
| Endpoint | P50 | P95 | P99 | Max RPS |
|----------|-----|-----|-----|---------|
| GET /api/tickers | <50ms | <200ms | <500ms | 5000 |
| GET /api/news | <50ms | <200ms | <500ms | 10000 |
| POST /api/tickers | <100ms | <500ms | <1000ms | 1000 |
| POST /api/alerts | <100ms | <500ms | <1000ms | 1000 |
| WebSocket connect | <200ms | <500ms | <1000ms | 2000 |

---

## Coverage Thresholds

| Layer | Current | Phase 1 Target | Phase 2 Target |
|-------|---------|----------------|----------------|
| Backend unit tests | ~60% | 80% | 90% |
| Backend integration | ~40% | 70% | 85% |
| Frontend components | ~30% | 60% | 80% |
| E2E critical flows | 0% | 100% of 5 core flows | 100% of 10+ flows |
| Load test baseline | None | Smoke + Load profiles | All 4 profiles |

---

## Scaling TODO

### Phase 1: Foundation
- [ ] Increase backend test coverage to 80%+ (add tests for chat, scheduler, providers, news, IPOs)
- [ ] Add frontend component tests for all components (WatchList, NewsFeed, ChatBox, IPOCalendar)
- [ ] Set up Playwright E2E framework with 5 core flow tests
- [ ] Create k6 smoke test script that runs in CI on every PR
- [ ] Add test coverage reporting to CI (codecov or similar)
- [ ] Add `conftest.py` fixtures for creating test users, tickers, alerts in one line
- [ ] Document test patterns in this file and enforce via PR reviews

### Phase 2: Scale
- [ ] Add k6 load + stress test profiles, run weekly on staging
- [ ] Add Playwright visual regression testing (screenshot comparison)
- [ ] Implement contract testing between Frontend and Backend (Pact or OpenAPI schema validation)
- [ ] Add chaos testing: kill backend during load test, verify graceful degradation
- [ ] Add database migration testing: run alembic upgrade/downgrade in CI
- [ ] Create synthetic monitoring: cron job that runs E2E smoke test against production every 5 min

### Phase 3: Global
- [ ] Multi-region latency benchmarks (test from US, EU, Asia)
- [ ] Performance regression detection in CI (compare P95 against baseline, fail if >20% worse)
- [ ] Add fuzzing for API endpoints (hypothesis library for Python)
- [ ] Implement test data management for load tests at scale (100K test users)
- [ ] Add accessibility testing automation (axe-core in Playwright)

---

## Running Tests

```bash
# Backend
cd backend
pytest tests/ -v                          # all tests
pytest tests/ -v --cov=app --cov-report=term  # with coverage
pytest tests/test_alerts.py -v -k "fires"  # specific tests

# Frontend
cd frontend
npm test                                   # watch mode
npm test -- --coverage --watchAll=false     # CI mode

# E2E (when set up)
cd tests/e2e
npx playwright test                        # headless
npx playwright test --ui                   # interactive mode

# Load (when set up)
cd tests/load
k6 run k6/smoke.js                         # smoke test
k6 run k6/load.js                          # load test
```

---

## PR Review Checklist (for reviewing other teams' PRs)

- [ ] New code paths have corresponding tests
- [ ] Tests are deterministic (no flaky time-dependent assertions)
- [ ] Mocks are scoped correctly (don't leak between tests)
- [ ] No `time.sleep()` in tests — use async waiters or mocked time
- [ ] Test names describe the scenario: `test_<what>_<condition>_<expected>`
- [ ] Integration tests clean up their data (use transactional fixtures)
- [ ] No hardcoded ports or URLs in tests — use fixtures/config
- [ ] Coverage on changed files is >=80%
