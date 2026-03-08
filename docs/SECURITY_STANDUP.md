# Security Review — Daily Standup Tracker

**Review Date:** 2026-03-08 · **Reviewer:** Security Engineering
**Format:** Check off items as they are merged to `main`. Update status daily at standup.
**Rule:** All security PRs require **Auth & Security team** mandatory review before merge.

---

## 🔐 Auth & Security Team

### 🔴 Critical — Must ship this sprint

- [ ] **JWT secret guard** — startup validation that blocks launch if `jwt_secret_key == "change-me-in-production"` in non-dev environments (`core/config.py`)
- [ ] **Token revocation** — Redis blocklist checked in `decode_access_token`; invalidate on logout (`core/auth.py`)
- [ ] **Rate limit `/auth/google`** — max 5 attempts per IP per minute (`api/auth.py`)
- [ ] **WebSocket alert PII** — strip `user_id` from broadcast payload OR scope to owning connection (`services/scheduler.py`) *(coordinate with Backend)*

### 🟠 High — This sprint

- [ ] **Symbol validation regex** — `^[\^]?[A-Z0-9.-]{1,20}$` on `TickerCreate.symbol` (`schemas/schemas.py`) *(coordinate with Backend)*
- [ ] **`ChatMessage` max length** — `Field(..., max_length=500)` (`schemas/schemas.py`) *(coordinate with Backend)*
- [ ] **`display_name` max length** — `Field(max_length=100)` on `UserUpdate` (`schemas/schemas.py`) *(coordinate with Backend)*
- [ ] **JWT expiry reduction** — design 15-min access token + 30-day refresh token flow *(design session with Backend + Frontend first)*
- [ ] **nginx security headers** — review DevOps PR for `nginx.conf` + `nginx.prod.conf`; approve CSP directives *(mandatory reviewer)*
- [ ] **JWT storage migration** — run joint design session with Frontend + Backend on moving away from localStorage *(kickoff session, not implementation)*

---

## 🐍 Backend Python Team

### 🔴 Critical — Must ship this sprint

- [ ] **Auth reminders — `POST /reminders`** — add `Depends(get_current_user)` + `user_id` FK on `Reminder` model (`api/routes.py`)
- [ ] **Auth reminders — `GET /reminders`** — add `Depends(get_current_user)`, filter by `user_id`
- [ ] **Auth reminders — `DELETE /reminders/{id}`** — add `Depends(get_current_user)`, ownership check

### 🟠 High — This sprint

- [ ] **Candles error leakage** — replace `detail=str(exc)` with generic `"Failed to fetch market data"` (`api/routes.py:347`)
- [ ] **Candles `days` bounds** — `Query(default=1, ge=1, le=365)` (`api/routes.py`)
- [ ] **News `limit` bounds** — `Query(default=50, ge=1, le=200)` (`api/routes.py`)
- [ ] **Symbol validation** — apply Auth team's regex to `TickerCreate.symbol` (`schemas/schemas.py`)
- [ ] **Chat message length** — `Field(..., min_length=1, max_length=500)` on `ChatMessage.message`
- [ ] **`display_name` length** — `Field(max_length=100)` on `UserUpdate.display_name`
- [ ] **SMTP TLS context** — add `context=ssl.create_default_context()` to `starttls()` call (`services/notification.py`)

### 🟡 Medium — Before next production deploy

- [ ] **Remove `create_all`** — replace with Alembic migrations; write initial migration files (`main.py` + `alembic/versions/`)
- [ ] **`/ready` endpoint** — add readiness probe that checks DB connectivity (`main.py`) *(DevOps contract)*

---

## ⚛️ Frontend React Team

### 🔴 Critical — Design first, then implement

- [ ] **JWT storage design session** — schedule joint session with Auth + Backend before writing any code *(prerequisite for implementation)*
- [ ] **JWT storage migration** — move away from `localStorage` to `HttpOnly` cookies or short-lived token pattern (`contexts/AuthContext.tsx`) *(after design session)*

### 🟠 High — This sprint

- [ ] **nginx security headers** — add Auth team's approved header block to `nginx.conf` and `nginx.prod.conf` *(Auth team mandatory reviewer)*

---

## 🧪 Test Engineering Team

### 🔴 Critical — Add after Backend fixes land

- [ ] **`test_reminders_unauthenticated_*`** — verify GET/POST/DELETE reminders correctly reject unauthenticated access after Backend PR merges (`tests/test_reminders.py`)
- [ ] **`test_auth_isolation`** — verify User A cannot read/modify/delete User B's watchlist, alerts, or reminders (`tests/security/test_auth_isolation.py`)

### 🟠 High — This sprint

- [ ] **Create `tests/security/`** — directory with `bandit_config.yaml`, `safety_check.sh`, `npm_audit.sh`
- [ ] **`test_ticker_symbol_validation`** — invalid patterns (`../../`, empty, 100+ chars) return 422 *(add after Auth schema PR merges)*
- [ ] **`test_chat_message_max_length`** — 501-char message returns 422 *(add after Backend PR merges)*
- [ ] **`test_candles_days_bounds`** — `days=-1` and `days=999999` return 400 *(add after Backend PR merges)*
- [ ] **`test_news_limit_capped`** — `limit=999999` returns 400 *(add after Backend PR merges)*
- [ ] **`test_display_name_max_length`** — 101-char name returns 422, not a DB error *(add after Backend PR merges)*

### 🟡 Medium — Phase 1

- [ ] **`test_websocket_alert_isolation`** — alert broadcast does not expose other users' data *(after Auth + Backend WS fix merges)*
- [ ] **Frontend `AuthContext` tests** — cover token storage key, token removal on logout, `X-Session-ID` header injection *(after JWT migration lands)*
- [ ] **E2E flow** — anonymous user cannot access another user's watchlist via direct URL (`tests/e2e/specs/auth-isolation.spec.ts`)

---

## 🚀 DevOps / CI-CD Team

### 🔴 Critical — Unblocks all other teams

- [ ] **GitHub Actions CI pipeline** — create `.github/workflows/ci.yml` with: test-backend → security-scan → lint → test-frontend → build

### 🟠 High — This sprint

- [ ] **Backend Dockerfile non-root user** — add `adduser appuser` + `USER appuser` before `EXPOSE` (`backend/Dockerfile`)
- [ ] **Frontend Dockerfile** — update `node:18-alpine` → `node:20-alpine`, `npm install --legacy-peer-deps` → `npm ci --production=false` (`frontend/Dockerfile`)
- [ ] **nginx security headers** — open PR adding Auth team's header block to both nginx configs *(Auth mandatory reviewer)*
- [ ] **Security scan jobs** — add `bandit`, `pip-audit`, `npm audit`, `trivy` to CI pipeline

### 🟡 Medium — This sprint

- [ ] **`deploy.sh` hardcoded values** — remove hardcoded `REACT_APP_GOOGLE_CLIENT_ID` fallback and CloudFront URL; use `${VAR:?Set VAR}` pattern (`deploy/aws/deploy.sh`)
- [ ] **`docker-compose.yml` credentials** — move `POSTGRES_PASSWORD` to `.env` file, document in `LOCAL_SETUP_GUIDE.md`

---

## 🤝 Cross-Team Design Sessions (Schedule This Week)

These items require multi-team alignment **before** any implementation. No team proceeds alone.

| Session | Teams | Owner | Status |
|---|---|---|---|
| JWT storage migration (localStorage → HttpOnly cookies or short-lived tokens) | Auth + Backend + Frontend | Auth team | ⬜ Not scheduled |
| WebSocket auth (scope alert delivery to owning user) | Auth + Backend | Auth team | ⬜ Not scheduled |
| Alembic initial migration (replace `create_all`) | Backend + DevOps | Backend team | ⬜ Not scheduled |
| `tests/security/` tooling setup | Test + Auth + DevOps | Test team | ⬜ Not scheduled |

---

## Standup Status Key

| Symbol | Meaning |
|---|---|
| ⬜ | Not started |
| 🔄 | In progress (add PR link) |
| ✅ | Merged to `main` |
| 🚫 | Blocked (add reason) |

---

## Progress Snapshot

| Team | Critical | High | Medium | Total Done |
|---|---|---|---|---|
| Auth & Security | 0 / 4 | 0 / 6 | — | 0 / 10 |
| Backend Python | 0 / 3 | 0 / 7 | 0 / 2 | 0 / 12 |
| Frontend React | 0 / 2 | 0 / 1 | — | 0 / 3 |
| Test Engineering | 0 / 2 | 0 / 5 | 0 / 3 | 0 / 10 |
| DevOps / CI-CD | 0 / 1 | 0 / 4 | 0 / 2 | 0 / 7 |
| **Total** | **0 / 12** | **0 / 23** | **0 / 7** | **0 / 42** |

> Update the progress snapshot counts at each standup as items are checked off.

---

*Security Engineering · FinMonitor · Last updated: 2026-03-08*
