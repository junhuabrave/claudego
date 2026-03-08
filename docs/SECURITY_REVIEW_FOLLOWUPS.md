# Security Review — Team Follow-Ups

**Date:** 2026-03-08
**Reviewer:** Security Engineering
**Scope:** Code (backend + frontend), Docker/containers, CI/CD, test coverage

> This document is the single reference for all security review action items. Each section is addressed to the owning team. Items are ordered by priority within each section. All security PRs require a mandatory review from the **Auth & Security team** before merging.

---

## Table of Contents

- [Auth & Security Team](#-auth--security-team)
- [Backend Python Team](#-backend-python-team)
- [Frontend React Team](#-frontend-react-team)
- [Test Engineering Team](#-test-engineering-team)
- [DevOps / CI-CD Team](#-devops--ci-cd-team)

---

## 🔐 Auth & Security Team

**Cc:** Backend team (coordination required on shared files)
**Priority:** Immediate — all items below are Phase 1 Critical from `auth-security.md`

Your `auth-security.md` is a solid spec. The problem is that **none of the Phase 1 "Do First" items have been implemented**. The code hasn't caught up to the plan. The following must land this sprint.

### `backend/app/core/config.py`

- **Hardcoded JWT secret with no enforcement guard.**
  ```python
  jwt_secret_key: str = "change-me-in-production"  # ← still the default
  ```
  If `.env` is missing in any environment, the app signs JWTs with a public default. Add a startup validator that raises on non-development environments if the default is detected.

- **30-day JWT expiry.** Your spec explicitly targets 15-minute access tokens + 30-day refresh tokens. The current single-token setup means a stolen JWT is valid for a month with no revocation path.

### `backend/app/core/auth.py`

- **No token revocation.** `logout()` on the frontend only removes the token from localStorage — it stays cryptographically valid until expiry. Your Phase 1 TODO calls for a Redis blocklist. This is required before 30-day tokens are acceptable in any deployment.

### `backend/app/api/auth.py`

- **No rate limiting on `POST /auth/google`.** Your spec mandates: *"Max 5 failed Google OAuth attempts per IP per hour."* Nothing is currently enforced.

### `backend/app/schemas/schemas.py` *(coordinate with Backend team)*

- **`TickerCreate.symbol: str`** — no regex, no length limit. Your spec lists the exact pattern to use:
  ```python
  SYMBOL_PATTERN = re.compile(r'^[\^]?[A-Z0-9.-]{1,20}$')
  ```
  It's not applied anywhere.

- **`ChatMessage.message: str`** — your spec says `max_length=500`. It's unbounded.

- **`UserUpdate.display_name`** — no `max_length`. DB column is `String(100)`; exceeding it triggers a raw DB error visible to the client.

### `frontend/nginx.conf` and `frontend/nginx.prod.conf` *(coordinate with DevOps)*

Zero security headers in either config. Your spec has the exact `add_header` block ready. This should be a DevOps PR but requires your mandatory sign-off before merge.

### `frontend/src/contexts/AuthContext.tsx` *(coordinate with Frontend team)*

JWT is stored in `localStorage`. Your rules state: *"Never store JWTs in cookies without HttpOnly, Secure, SameSite=Strict flags"* — localStorage is worse; any script can access it. Coordinate with Frontend on migrating to `HttpOnly` cookies or the short-lived access token pattern. Do not implement unilaterally — open a joint design session first.

### 🚨 Critical Issue Not in Your Phase 1 List

The WebSocket endpoint broadcasts price alerts to **all connected clients**, including `user_id`, `symbol`, and `threshold_pct`. Your `backend-python.md` notes this: *"avoid adding more user-identifying data to broadcasts"* — but the current `check_price_alerts()` broadcast already leaks it. This directly violates your own rule: *"Never broadcast sensitive user data via WebSocket."*

Coordinate with Backend to either strip `user_id` from the broadcast payload immediately, or scope delivery to authenticated connections. This must be resolved before the next release.

---

## 🐍 Backend Python Team

**Cc:** Auth & Security team (mandatory reviewer on all items below)
**Priority:** Phase 1 — several items block security sign-off

### `backend/app/api/routes.py`

1. **Reminders endpoints are fully unauthenticated.**
   `POST /reminders`, `GET /reminders`, and `DELETE /reminders/{id}` have no `Depends(get_current_user)`. Consequences:
   - Any anonymous caller can **list all reminders**, including `notify_address` (email addresses, PagerDuty routing keys)
   - Anyone can **create reminders** targeting arbitrary email addresses (spam/abuse vector)
   - Anyone can **delete any reminder** by guessing an integer ID

   Add `current_user: User = Depends(get_current_user)` to all three endpoints and add a `user_id` FK to the `Reminder` model. Coordinate with Auth team on the model change.

2. **`GET /candles/{symbol}` leaks exception detail.**
   ```python
   raise HTTPException(status_code=502, detail=str(exc))  # ← exposes internals
   ```
   Per your own error handling standard: *"Never return raw exception messages to clients."* Log the exception and return a generic `"Failed to fetch market data"` message.

3. **`days` parameter on `/candles/{symbol}` is unbounded.**
   An arbitrarily large value triggers a slow/failing external API call. Add:
   ```python
   days: int = Query(default=1, ge=1, le=365)
   ```

4. **`limit` on `GET /news` is unbounded.**
   Same pattern — cap with:
   ```python
   limit: int = Query(default=50, ge=1, le=200)
   ```

5. **WebSocket alert broadcast leaks `user_id` to all clients.**
   Your `backend-python.md` already acknowledges this: *"Alert broadcasts currently include `user_id` and go to ALL connected clients."* This is a live PII leak. Coordinate with Auth team on the interim approach — either strip `user_id` from the broadcast payload now, or scope delivery to authenticated connections.

### `backend/app/schemas/schemas.py`

1. **`TickerCreate.symbol`** — no validation. Auth team owns the regex spec. Coordinate, then add as a `pattern=` Field constraint.
2. **`ChatMessage.message`** — add `Field(..., min_length=1, max_length=500)`.
3. **`UserUpdate.display_name`** — add `max_length=100` to match the DB column and prevent truncation errors surfacing to clients.

### `backend/app/services/notification.py`

`smtplib.SMTP.starttls()` is called without an explicit SSL context, leaving the SMTP upgrade vulnerable to MITM. Fix:
```python
import ssl
ctx = ssl.create_default_context()
server.starttls(context=ctx)
```

### `backend/app/main.py`

`Base.metadata.create_all` runs at every startup. Your own standard is clear: *"Never use `Base.metadata.create_all()` in production — use Alembic migrations."* The `alembic/versions/` directory is currently empty. Switch to Alembic before the next production deploy.

---

## ⚛️ Frontend React Team

**Cc:** Auth & Security team (mandatory reviewer on both items below)
**Priority:** Phase 1 — one critical item, one high

### `frontend/src/contexts/AuthContext.tsx`

The JWT is stored in `localStorage` (`finmonitor_token`). This exposes the token to any JavaScript running on the page — including third-party scripts and any future XSS vulnerability. The Auth team's spec flags this as a Phase 1 item.

**Target approach** (coordinate with Auth team before implementing):
- Move to `HttpOnly; Secure; SameSite=Strict` cookies managed by the backend, **or**
- Implement short-lived access tokens (15 min) where the refresh token is server-side only

This is an Auth + Backend + Frontend joint effort and needs a shared design session before any code is written. **Do not implement unilaterally.** Open a design discussion with Auth team first.

### `frontend/nginx.conf` and `frontend/nginx.prod.conf`

Neither config has any HTTP security headers. Your team owns both files. The Auth team's spec has the exact header block ready to copy in, covering:

| Header | Purpose |
|---|---|
| `Content-Security-Policy` | XSS protection |
| `Strict-Transport-Security` | Prevents HTTPS downgrade |
| `X-Content-Type-Options` | Blocks MIME sniffing |
| `X-Frame-Options` | Prevents clickjacking |
| `Referrer-Policy` | Limits information leakage |
| `Permissions-Policy` | Restricts browser feature access |

Coordinate with Auth for CSP review before merging, and confirm the CSP `connect-src` directives cover all production endpoints (CloudFront, Finnhub, Google Accounts).

> **Note on CSP + MUI:** MUI injects inline styles, so `style-src 'self' 'unsafe-inline'` is required for now. The Auth spec accounts for this. A `nonce`-based approach is a Phase 2 consideration.

---

## 🧪 Test Engineering Team

**Cc:** All teams
**Priority:** Phase 1 — create `tests/security/` (your file per team standards) and fill critical gaps

The review found coverage gaps specifically around **access control logic** — the category of bug that is invisible until it's exploited. Your team owns `tests/security/` (currently doesn't exist) and has shared ownership of backend and frontend test suites.

### Missing Backend Tests (`backend/tests/`)

| Test to add | Why it matters |
|---|---|
| `test_reminders_unauthenticated_list_exposes_email` | `GET /reminders` returns all `notify_address` fields to anyone — no auth currently required |
| `test_reminders_unauthenticated_create_any_address` | `POST /reminders` accepts arbitrary email addresses without auth |
| `test_reminders_delete_any_by_id` | `DELETE /reminders/{id}` has no ownership check |
| `test_alert_broadcast_does_not_leak_other_users_data` | WS alert payloads include `user_id` and reach all connections |
| `test_ticker_symbol_rejects_invalid_patterns` | Once schema validation is added — verify `../../`, empty strings, 100-char inputs are blocked |
| `test_chat_message_rejects_oversized_input` | Once `max_length=500` is added — verify 422 is returned |
| `test_candles_rejects_invalid_days` | `days=-1` and `days=999999` should return 400 once bounds are enforced |
| `test_news_limit_capped_at_200` | `limit=999999` should be rejected |
| `test_display_name_rejects_over_100_chars` | Should return 422, not a DB truncation error |

### New Directory — `tests/security/` *(your file to create)*

Per `TEAMS_OVERVIEW.md`, this directory is listed as NEW and jointly owned with Auth team. Priority items:

1. **`bandit_config.yaml`** — SAST config for Python source scan:
   ```bash
   bandit -r backend/app/ -c tests/security/bandit_config.yaml
   ```
   Run in CI on every PR.

2. **`safety_check.sh`** — Python dependency CVE scan:
   ```bash
   pip-audit -r backend/requirements.txt
   ```

3. **`npm_audit.sh`** — Frontend dependency CVE scan:
   ```bash
   npm audit --prefix frontend
   ```

4. **`test_auth_isolation.py`** — Parametrized tests verifying User A **cannot** read, modify, or delete User B's watchlist entries, alerts, or reminders. This is the highest-priority security test for a multi-user financial app.

### Missing Frontend Tests (`frontend/src/__tests__/`)

`AuthContext.test.tsx` exists but does not cover:
- Token storage location (correct localStorage key is used)
- Token removal on logout
- `X-Session-ID` header sent on every request

Once the JWT storage migration is implemented (coordinated with Auth + Frontend teams), add tests verifying the new storage mechanism behaves correctly.

### E2E Suggestion

Your Phase 1 E2E spec lists `login.spec.ts` as one of 5 core flows. Add a security-focused scenario:

> *"Anonymous user cannot access another user's watchlist by navigating directly to a watchlist URL."*

This validates the auth boundary at the UI level, not just the API level.

---

## 🚀 DevOps / CI-CD Team

**Cc:** All teams
**Priority:** Phase 1 — no CI pipeline is the biggest structural gap; container security is second

The deployment contract in `TEAMS_OVERVIEW.md` is largely aspirational — the pipeline described there doesn't exist yet.

### No CI Pipeline Exists

There are no `.github/workflows/` files. Per the deployment contract: *"Docker images must pass security scan (Trivy) before merge"* — this is unenforceable without a pipeline. Your `devops-cicd.md` already has the GitHub Actions template. Recommended job priority order:

| Priority | Job | Command |
|---|---|---|
| 1 | `test-backend` | `pytest tests/ -v --cov=app` |
| 2 | `security-scan` | `bandit` + `pip-audit` + `npm audit` + `trivy image` |
| 3 | `lint-backend` | `ruff check backend/` + `mypy app/ --strict` |
| 4 | `lint-frontend` | `tsc --noEmit` |
| 5 | `test-frontend` | `npm test -- --coverage --watchAll=false` |
| 6 | `build` | `docker build` both images on every PR |

The security scan job has the highest ROI — it will immediately surface dependency vulnerabilities that are currently invisible.

### `backend/Dockerfile` — Container Runs as Root

Your own Docker standards include the non-root user pattern — it's not in the current file:

```dockerfile
# Add before EXPOSE
RUN adduser --disabled-password --gecos "" appuser
USER appuser
```

The container currently runs as root. A container escape or SSRF gives full root access to the filesystem.

### `frontend/Dockerfile` — `--legacy-peer-deps` and Wrong Node Version

| Current | Target (per your devops-cicd.md standard) |
|---|---|
| `node:18-alpine` | `node:20-alpine` |
| `npm install --legacy-peer-deps` | `npm ci --production=false` |

`npm ci` uses the lockfile exactly and is safer than `npm install`. `--legacy-peer-deps` skips peer dependency conflict resolution and can silently allow incompatible, potentially vulnerable package versions. Fix both in the same PR.

### `docker-compose.yml` — Default PostgreSQL Credentials

`POSTGRES_PASSWORD: postgres` is hardcoded. Move to a `.env` file even for local dev, and document the setup in `docs/LOCAL_SETUP_GUIDE.md`. This prevents the credential leaking into staging if `.env` management is inconsistent.

### `deploy/aws/deploy.sh` — Hardcoded Infrastructure Values

Two values should not have hardcoded defaults:

```bash
# Current — hardcoded fallback
REACT_APP_GOOGLE_CLIENT_ID="${REACT_APP_GOOGLE_CLIENT_ID:-536860413974-...}"

# Current — fully hardcoded
--build-arg REACT_APP_WS_URL=wss://d1yleiq0s9sk4n.cloudfront.net/api/ws
```

Use the `${VAR:?Set VAR}` pattern (already used for `AWS_ACCOUNT_ID`) to make these required with no fallback. This also makes multi-environment deployments cleaner.

### Missing: `/ready` Endpoint

Your standards require both `/health` (liveness) and `/ready` (readiness, checks DB connectivity). Only `/health` exists. Per the deployment contract, all services must expose both. Coordinate with Backend team to add `/ready` — it's a Backend file, but a DevOps contract requirement needed for ECS health checks and accurate auto-scaling.

### Recommended PR Sequencing

```
1. CI pipeline        → unblocks everything (tests, scans, build validation)
2. Dockerfile fixes   → non-root user, npm ci, Node 20
3. nginx headers      → coordinate with Auth for CSP review, Frontend for file ownership
4. deploy.sh cleanup  → remove hardcoded values
```

---

## Cross-Team: Open Design Sessions Needed

The following items require multi-team alignment before any implementation starts. No team should proceed unilaterally.

| Topic | Teams | Urgency |
|---|---|---|
| JWT storage migration (localStorage → HttpOnly cookies or short-lived tokens) | Auth + Backend + Frontend | High — must be designed before Frontend implements anything |
| WebSocket authentication (scope alert delivery to owning user) | Auth + Backend | High — live PII leak in current broadcasts |
| Alembic migration strategy (replace `create_all`, write initial migrations) | Backend + DevOps | High — required before next schema change |
| `tests/security/` ownership and tooling setup | Test + Auth + DevOps | Medium — coordinate with CI pipeline work |

---

*Generated by Security Engineering · FinMonitor Security Review · 2026-03-08*
*All PRs touching auth, CORS, headers, or secrets require Auth & Security team review before merge.*
