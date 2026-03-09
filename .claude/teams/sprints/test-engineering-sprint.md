# Test Engineering Team — Phase 1 Completion Sprint

**Sprint Duration:** 2 weeks
**Team Lead:** Test Engineering Team
**Reference:** [test-engineering.md](../test-engineering.md) for coding standards

---

## Sprint Goal

Close the **critical test coverage gaps**: backend has no tests for chat, scheduler, or providers; frontend has zero component tests. By end of sprint, we need 80% backend coverage and tests for all 7 major frontend components.

---

## Current State

| Area | Coverage | Status |
|------|----------|--------|
| Backend auth routes | ~70% | Partial — login + me tested, edge cases missing |
| Backend API routes | ~60% | Partial — CRUD tested, WebSocket untested |
| Backend chat service | 0% | Not started |
| Backend scheduler | 0% | Not started |
| Backend providers | 0% | Not started |
| Frontend components | 0% | Not started (Jest configured but no tests) |
| E2E tests | 0% | Not started |

---

## Tasks

### Task 1: Backend Test Coverage — Chat Service (P0) — 1.5 days

**Target file:** `backend/app/services/chat.py`

**Tests to write in `backend/tests/test_chat.py`:**

```python
# Test parse_chat_message with various inputs
async def test_chat_add_ticker():
    """'add AAPL' should return action='added_ticker', ticker='AAPL'"""

async def test_chat_remove_ticker():
    """'remove MSFT' should return action='removed_ticker', ticker='MSFT'"""

async def test_chat_unknown_command():
    """Random text should return helpful reply, action=None"""

async def test_chat_symbol_normalization():
    """'add aapl' should normalize to 'AAPL'"""

async def test_chat_message_too_long():
    """500+ char message handled gracefully"""
```

**Key patterns from conftest.py:**
- Use `client` fixture for HTTP tests
- Use `auth_headers(token)` for authenticated requests
- Use `anon_headers` for anonymous session requests

**Acceptance Criteria:**
- [ ] All chat parse paths tested (add, remove, unknown)
- [ ] Symbol normalization verified
- [ ] Edge cases: empty string, special characters, SQL-injection-like input

---

### Task 2: Backend Test Coverage — Scheduler (P0) — 1.5 days

**Target file:** `backend/app/services/scheduler.py`

**Important:** Scheduler uses `async_session()` directly (not `get_db()` dependency). Tests need to mock at the session factory level.

**Tests to write in `backend/tests/test_scheduler.py`:**

```python
# Mock the provider + session
async def test_poll_news_inserts_new_articles():
    """New articles get inserted via pg_insert on_conflict_do_nothing"""

async def test_poll_news_skips_duplicates():
    """Articles with existing external_id are not duplicated"""

async def test_poll_quotes_updates_ticker_prices():
    """Quotes update Ticker.last_price and Ticker.change_percent"""

async def test_check_price_alerts_fires_on_threshold():
    """Alert with threshold_pct=5, direction='up', change=6% should fire"""

async def test_check_price_alerts_respects_cooldown():
    """Alert fired 2 min ago should not re-fire (cooldown default 30 min)"""

async def test_check_price_alerts_direction_down():
    """direction='down' only fires on negative change"""

async def test_check_price_alerts_direction_both():
    """direction='both' fires on abs(change) >= threshold"""
```

**Caveat:** `pg_insert` (PostgreSQL dialect) doesn't work in SQLite test DB. Either:
- Mock `session.execute` for the pg_insert calls
- Or use a PostgreSQL test DB in CI (coordinate with DevOps)

**Acceptance Criteria:**
- [ ] All poll functions tested with mocked providers
- [ ] Price alert threshold logic tested for all 3 directions
- [ ] Cooldown logic tested
- [ ] WebSocket broadcast called with correct payload

---

### Task 3: Backend Test Coverage — Providers (P0) — 1 day

**Target files:** `backend/app/providers/` (finnhub.py, alpha_vantage.py, yfinance_provider.py)

**Tests to write in `backend/tests/test_providers.py`:**

```python
# Mock httpx/aiohttp responses
async def test_finnhub_news_parses_response():
    """Finnhub API response maps to NewsArticle dict correctly"""

async def test_finnhub_ipo_parses_response():
    """Finnhub IPO calendar maps to IPOEvent dict correctly"""

async def test_alpha_vantage_quote_parses_response():
    """Alpha Vantage quote endpoint maps correctly"""

async def test_yfinance_handles_nan():
    """yfinance returning NaN/Inf should be sanitized to None"""

async def test_provider_factory_returns_correct_type():
    """get_news_provider() returns FinnhubProvider when key configured"""
```

**Acceptance Criteria:**
- [ ] Each provider's response parsing is tested
- [ ] NaN/Inf handling in yfinance tested
- [ ] Factory functions return correct provider types

---

### Task 4: Frontend Component Tests (P0) — 5 days

**All 7 major components need tests.** Use React Testing Library + Jest.

**Setup in `frontend/src/setupTests.ts`:**
```typescript
import "@testing-library/jest-dom";
```

**Components to test:**

| Component | Priority Test Cases | File |
|-----------|-------------------|------|
| Dashboard | Renders ticker grid, handles empty state | `Dashboard.test.tsx` |
| NewsFeed | Renders article list, links open in new tab | `NewsFeed.test.tsx` |
| IPOCalendar | Renders IPO table, date formatting | `IPOCalendar.test.tsx` |
| TickerDetail | Renders chart placeholder, handles missing data | `TickerDetail.test.tsx` |
| ChatWidget | Sends message, displays response | `ChatWidget.test.tsx` |
| PriceAlertPanel | Lists alerts, toggle active/inactive | `PriceAlertPanel.test.tsx` |
| Header/Nav | Login button, user menu, logout | `Header.test.tsx` |

**Pattern for all component tests:**

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AuthProvider } from "../contexts/AuthContext";

// Mock API calls
jest.mock("../services/api", () => ({
  getTickers: jest.fn().mockResolvedValue({ data: [...] }),
}));

// Wrap with providers
const renderWithProviders = (ui: React.ReactElement) => {
  return render(<AuthProvider>{ui}</AuthProvider>);
};

test("renders ticker symbols", async () => {
  renderWithProviders(<Dashboard />);
  await waitFor(() => {
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });
});
```

**Acceptance Criteria:**
- [ ] All 7 components have test files
- [ ] Each test file covers: render, user interaction, error state
- [ ] `npm test` passes with all tests
- [ ] Tests run in CI (already configured in ci.yml)

---

### Task 5: Playwright E2E Setup + 3 Core Flows (P1) — 3 days

**Blocked by:** Staging environment (DevOps Task 1). Start setup locally; point at staging when ready.

**Setup:**
```bash
cd frontend
npm install -D @playwright/test
npx playwright install
```

**3 Core Flows:**

1. **Anonymous user flow:**
   - Load dashboard → see default tickers
   - Add ticker via chat → ticker appears in grid
   - Remove ticker → ticker disappears

2. **Google login flow:**
   - Click login → mock Google OAuth
   - Verify user name shows in header
   - Verify watchlist is user-specific

3. **Price alert flow:**
   - Login → create price alert
   - Verify alert appears in list
   - Toggle alert inactive → verify state change

**Acceptance Criteria:**
- [ ] Playwright config exists with baseURL pointing to staging
- [ ] 3 E2E tests pass against staging
- [ ] Tests run in CI on `main` branch merges (not on every PR — too slow)

---

### Task 6: k6 Smoke Test (P1) — 1 day

**Setup `tests/k6/smoke.js`:**

```javascript
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 10,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<1000"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const base = __ENV.BASE_URL || "http://localhost:8000";

  // Health check
  let res = http.get(`${base}/health`);
  check(res, { "health 200": (r) => r.status === 200 });

  // Tickers
  res = http.get(`${base}/api/tickers`);
  check(res, { "tickers 200": (r) => r.status === 200 });

  // News
  res = http.get(`${base}/api/news`);
  check(res, { "news 200": (r) => r.status === 200 });

  sleep(1);
}
```

**Acceptance Criteria:**
- [ ] k6 smoke test passes locally
- [ ] P95 latency < 1s with 10 VUs
- [ ] Error rate < 1%
- [ ] Integrated into CI as optional job

---

## Coordination

- **With Backend:** Need `fakeredis` fixture in conftest.py once Redis is integrated. Scheduler tests need careful mocking — ask backend team about `async_session` mock pattern.
- **With Frontend:** ESLint config (Task 1 in frontend sprint) should land before we add test files, to avoid lint conflicts.
- **With DevOps:** E2E tests need staging URL. k6 needs staging URL for meaningful results.

---

## Out of Scope This Sprint

- Contract testing (Phase 2)
- Visual regression testing (Phase 2)
- Chaos testing (Phase 2)
- Load testing at 500+ users (Phase 2)
- Coverage reporting to Codecov (nice-to-have, do if time permits)

---

*Questions? Tag @test-lead in the PR or post in #test-engineering channel.*
