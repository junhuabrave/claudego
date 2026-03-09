# Auth/Security Team — Phase 1 Completion Sprint

**Sprint Duration:** 2 weeks
**Team Lead:** Auth/Security Team
**Reference:** [auth-security.md](../auth-security.md) for coding standards

---

## Sprint Goal

Close the two remaining P0 security gaps: **rate limiting** (we are currently open to abuse) and **refresh tokens** (JWT access tokens have no expiry rotation). These are hard blockers for any public-facing scale.

---

## Tasks

### Task 1: Rate Limiting Middleware (P0) — 3 days

**Why:** Zero rate limiting means any client can hammer the API. A single script could take down the service. This is the #1 security risk at scale.

**Implementation:**

1. Add `slowapi` to requirements.txt (built on `limits`, works with FastAPI):
   ```bash
   pip install slowapi
   ```

2. Create `app/core/rate_limit.py`:
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   from app.core.config import settings

   # Use Redis backend for distributed rate limiting across instances
   limiter = Limiter(
       key_func=get_remote_address,
       storage_uri=settings.redis_url,
       default_limits=["100/minute"],
   )
   ```

3. Register in `main.py`:
   ```python
   from slowapi import _rate_limit_exceeded_handler
   from slowapi.errors import RateLimitExceeded
   from app.core.rate_limit import limiter

   app.state.limiter = limiter
   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
   ```

4. Apply per-route where needed:
   ```python
   # Stricter limit on auth endpoint (prevent credential stuffing)
   @router.post("/auth/google")
   @limiter.limit("10/minute")
   async def google_login(request: Request, ...):

   # Stricter limit on chat (LLM cost)
   @router.post("/chat")
   @limiter.limit("20/minute")
   async def chat(request: Request, ...):

   # Default 100/min applies to all other routes
   ```

5. Add to `app/core/config.py`:
   ```python
   rate_limit_default: str = "100/minute"
   rate_limit_auth: str = "10/minute"
   rate_limit_chat: str = "20/minute"
   ```

6. Return proper headers:
   ```
   X-RateLimit-Limit: 100
   X-RateLimit-Remaining: 95
   X-RateLimit-Reset: 1709942400
   ```

**Important:** Uses Redis backend (same instance as cache). Coordinate with Backend team on `REDIS_URL`.

**Testing:**
- Unit test: verify 429 returned after limit exceeded
- Integration test: verify Redis stores counters correctly
- Test: verify rate limit headers present in response

**Acceptance Criteria:**
- [ ] Default 100 req/min per IP on all endpoints
- [ ] Auth endpoint limited to 10 req/min
- [ ] Chat endpoint limited to 20 req/min
- [ ] 429 response with Retry-After header when exceeded
- [ ] Rate limit headers on every response
- [ ] Works across multiple backend instances (Redis-backed)

---

### Task 2: Refresh Token Flow (P0) — 3 days

**Why:** Current JWT tokens have no rotation. If stolen, they're valid until expiry. Refresh tokens allow short-lived access tokens with secure rotation.

**Implementation:**

1. Update `app/core/config.py`:
   ```python
   access_token_expire_minutes: int = 15      # was: jwt_expiration_hours * 60
   refresh_token_expire_days: int = 30
   ```

2. Create refresh token model in `app/models/models.py`:
   ```python
   class RefreshToken(Base):
       __tablename__ = "refresh_tokens"
       id: Mapped[int] = mapped_column(primary_key=True)
       user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
       token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
       expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
       revoked: Mapped[bool] = mapped_column(default=False)
       created_at: Mapped[datetime] = mapped_column(server_default=func.now())
   ```

3. Generate Alembic migration:
   ```bash
   alembic revision --autogenerate -m "add refresh_tokens table"
   alembic upgrade head
   ```

4. Update `app/api/auth.py` — login returns both tokens:
   ```python
   # On successful Google login:
   access_token = create_access_token(user.id)   # 15 min
   refresh_token = create_refresh_token(user.id)  # 30 days, stored hashed in DB
   return {
       "access_token": access_token,
       "refresh_token": refresh_token,
       "token_type": "bearer",
       "expires_in": 900,  # seconds
       "user": UserResponse.model_validate(user),
   }
   ```

5. Add refresh endpoint:
   ```python
   @router.post("/auth/refresh")
   async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
       old_refresh = request.headers.get("X-Refresh-Token")
       # Validate, rotate (revoke old, issue new), return new pair
   ```

6. **Frontend update needed:** `AuthContext.tsx` must:
   - Store refresh token in `localStorage` (separate key)
   - Add axios interceptor: on 401, try refresh before redirecting to login
   - Clear both tokens on logout

**Security Considerations:**
- Store refresh token hash in DB (bcrypt), never the raw token
- Rotate on every use (revoke old, issue new)
- Revoke all refresh tokens on logout (`DELETE WHERE user_id = ?`)
- Rate limit /auth/refresh to 5/minute

**Testing:**
- Test: access token expires, refresh returns new pair
- Test: revoked refresh token returns 401
- Test: refresh token rotation (old token invalid after use)

**Acceptance Criteria:**
- [ ] Login returns access_token (15 min) + refresh_token (30 day)
- [ ] POST /auth/refresh rotates tokens
- [ ] Revoked tokens return 401
- [ ] Logout revokes all refresh tokens for user
- [ ] Frontend interceptor handles silent refresh
- [ ] Alembic migration for refresh_tokens table

---

### Task 3: Input Validation Audit (P1) — 1 day

**Why:** Some endpoints still accept unchecked input. Audit all routes for missing validation.

**Checklist:**

| Endpoint | Current Validation | Action Needed |
|----------|-------------------|---------------|
| POST /auth/google | credential: str | Add max_length=4096 |
| POST /chat | message: 1-500 chars | Already done |
| POST /tickers | symbol regex | Already done |
| POST /alerts | threshold + direction | Already done |
| POST /reminders | ipo_event_id: int | Add FK existence check |
| PUT /alerts/{id} | partial update | Already done |
| PUT /user/profile | display_name: max 100 | Already done |
| WebSocket messages | type checked | Add max message size (4KB) |

**Acceptance Criteria:**
- [ ] All endpoints have documented max_length on string fields
- [ ] WebSocket rejects messages > 4KB
- [ ] FK references validated before insert

---

## Coordination

- **With Backend:** Share Redis connection via `get_redis()` singleton. Rate limiting and cache use same Redis instance.
- **With Frontend:** Refresh token flow requires AuthContext.tsx changes. Provide the API contract:
  - `POST /auth/google` → `{ access_token, refresh_token, expires_in, user }`
  - `POST /auth/refresh` with `X-Refresh-Token` header → same response
  - Frontend should retry on 401 with refresh token before redirecting to login
- **With DevOps:** Need `REDIS_URL` in staging environment variables.

---

## Out of Scope This Sprint

- RBAC system (Phase 2)
- GitHub OAuth provider (Phase 2)
- Authenticated WebSocket (Phase 2)
- GDPR account deletion (Phase 2)
- API key management (Phase 2)

---

*Questions? Tag @auth-lead in the PR or post in #auth-security channel.*
