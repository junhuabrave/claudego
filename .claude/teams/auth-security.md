# Auth & Security Engineering — Team Standards

> Load this file as agent context when working on authentication, authorization, and security.

## Team Scope

You own **authentication, authorization, secrets management, and security hardening** across the entire project.

**Your files:**
- `backend/app/core/auth.py` — JWT encoding/decoding, `get_current_user` dependency
- `backend/app/api/auth.py` — Google OAuth routes, user profile endpoints
- `backend/app/models/models.py` — `User` model schema (you own schema changes to this table)
- `backend/app/core/config.py` — Auth-related settings (JWT, Google, premium gating)
- `frontend/src/contexts/AuthContext.tsx` — Auth state management (shared with Frontend team)
- `tests/security/` — Security scanning configs (NEW — you create this)

**Your responsibilities:**
- Own the authentication flow (anonymous → Google OAuth → JWT)
- Define and enforce authorization rules (per-user data isolation, premium gating)
- Implement rate limiting and abuse prevention
- Manage secrets rotation strategy
- Conduct security reviews on all PRs
- Ensure compliance readiness (GDPR, SOC2)

**Not your files:**
- Business logic endpoints → Backend team (but you review for auth correctness)
- Frontend components → Frontend team (but you review AuthContext changes)
- Infrastructure/deployment → DevOps team (but you define secrets management policy)

---

## Security Standards

### Authentication Architecture

#### Current Flow
```
1. Anonymous: X-Session-ID header → find-or-create User(session_id=UUID)
2. Google OAuth: credential → verify with google-auth → create/promote User → return JWT
3. JWT: Authorization: Bearer <token> → decode → get user_id → load User
```

#### Target Flow (Phase 2+)
```
1. Anonymous: Same as current (temporary identity)
2. OAuth: Google + GitHub + Microsoft SSO (enterprise)
3. JWT: Short-lived access tokens (15 min) + refresh tokens (30 days)
4. API Keys: For programmatic access (premium users)
5. Session Management: Token revocation list in Redis
```

### JWT Standards
```python
# Current implementation — needs improvement
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30  # Too long for production

# Target implementation
JWT_ALGORITHM = "HS256"           # Consider RS256 for multi-service
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived access token
REFRESH_TOKEN_EXPIRE_DAYS = 30    # Long-lived refresh token
```

**Rules:**
- **Never** store JWTs in cookies without `HttpOnly`, `Secure`, `SameSite=Strict` flags
- **Always** validate `exp` claim — reject expired tokens immediately
- **Always** validate `sub` claim — ensure user exists in database
- **Never** put sensitive data in JWT payload (it's base64, not encrypted)
- JWT secret must be at least 256 bits — generated via `openssl rand -hex 32`
- Rotate JWT secret quarterly — old tokens become invalid (acceptable for 15-min access tokens)

### Authorization Rules
```python
# Every endpoint that accesses user data MUST use this dependency
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    # 1. Check Authorization header (JWT) first
    # 2. Fall back to X-Session-ID header (anonymous)
    # 3. Raise 401 if neither present
    ...
```

**Data isolation rules:**
- User A can **never** read, modify, or delete User B's data
- All queries on user-owned tables **must** include `WHERE user_id = current_user.id`
- Admin endpoints (future) require separate `get_admin_user` dependency
- Premium feature gating uses `user.tier` check — never trust client-side tier claims

### Rate Limiting (NEW — Priority)
```python
# Implement rate limiting middleware
# Use sliding window algorithm with Redis backend

RATE_LIMITS = {
    "default": "100/minute",        # General API
    "auth": "10/minute",            # Login attempts
    "create": "30/minute",          # POST endpoints
    "websocket": "5/minute",        # WS connection attempts
}
```

- Rate limit by IP for anonymous users, by user_id for authenticated users
- Return `429 Too Many Requests` with `Retry-After` header
- Log rate limit hits for abuse detection
- Whitelist internal health check IPs

### Input Validation & Sanitization
```python
# ALREADY IMPLEMENTED in schemas.py:
class PriceAlertCreate(BaseModel):
    threshold_pct: float = Field(gt=0, le=100)                          # range validation ✓
    direction: str = Field(default="both", pattern="^(up|down|both)$")  # enum validation ✓

class TickerResponse(BaseModel):
    @field_validator("last_price", "change_percent", mode="before")
    def sanitize_float(cls, v):  # NaN/Inf → None ✓

# NEEDS TO BE ADDED (Phase 1):
# 1. Symbol validation on TickerCreate — currently accepts any string
SYMBOL_PATTERN = re.compile(r'^[\^]?[A-Z0-9.-]{1,20}$')

# 2. String length limit on ChatMessage — currently unbounded
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)

# 3. Request body size limit in uvicorn/nginx — currently unlimited
```

- **Never** construct SQL from user input — always use SQLAlchemy ORM
- **Never** render user input as HTML without escaping (React handles this)
- **Always** validate and sanitize at the API boundary (Pydantic schemas)
- **Always** use parameterized queries — never string interpolation in SQL

### Secrets Management
```
# Current: .env files and hardcoded defaults
jwt_secret_key: str = "change-me-in-production"  # BAD

# Target: External secrets store
# AWS: Secrets Manager → injected as env vars by ECS
# GCP: Secret Manager → mounted as volumes
# Azure: Key Vault → injected by Container Apps
```

**Rules:**
- **Never** commit secrets to git — use `.env.example` with placeholders
- **Never** log secrets — mask sensitive values in structured logs
- **Never** return secrets in API responses
- Rotate API keys (Finnhub, Alpha Vantage) quarterly
- JWT secret rotation: generate new secret, old tokens expire naturally (15 min with short-lived tokens)
- Database passwords: rotate monthly, use IAM auth where possible (RDS IAM)

### HTTP Security Headers (nginx)
```nginx
# Required headers for production
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://accounts.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self' https://accounts.google.com; frame-src https://accounts.google.com; font-src 'self'" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# NOTE: Do NOT add X-XSS-Protection — it is deprecated in modern browsers
# and can introduce vulnerabilities in IE. CSP provides better XSS protection.

# connect-src notes:
#   - 'self' covers all /api/* REST calls and /api/ws WebSocket (same-origin via proxy)
#   - wss: wildcard intentionally excluded — 'self' is tighter and sufficient
#   - finnhub.io and alphavantage.co intentionally excluded — backend-only, browser
#     never calls these directly
#   - style-src 'unsafe-inline' required by MUI/emotion; remove in Phase 2 (Vite + nonce)
```

### CORS Configuration
```python
# Restrict CORS to known origins only
CORS_ORIGINS = {
    "development": ["http://localhost:3000", "https://localhost:3443"],
    "production": ["https://finmonitor.example.com"],  # Exact domain
}
# Never use "*" in production
```

### WebSocket Security
- WebSocket connections are currently **unauthenticated** (broadcast model)
- **Phase 2**: Add JWT-based WebSocket authentication
  - Client sends JWT in first message after connection
  - Server validates and associates connection with user_id
  - User-specific alerts only sent to authenticated connections
- **Never** broadcast sensitive user data (emails, settings) via WebSocket
- Implement connection limits: max 5 concurrent WS per user

---

## Compliance Roadmap

### GDPR (Required for EU users)
- [ ] Add `DELETE /api/auth/me` endpoint — delete user account and all associated data
- [ ] Add data export endpoint — return all user data as JSON
- [ ] Add privacy policy page to frontend
- [ ] Add cookie consent banner (for analytics, not for functional cookies)
- [ ] Implement data retention policy: auto-delete inactive accounts after 12 months
- [ ] Document data processing in a GDPR compliance doc

### SOC2 Preparation
- [ ] Enable audit logging: log all auth events (login, logout, token refresh, failed attempts)
- [ ] Implement access controls: admin/user roles with distinct permissions
- [ ] Document incident response procedure
- [ ] Enable encryption at rest (RDS encryption, S3 encryption)
- [ ] Enable encryption in transit (TLS everywhere, no HTTP)
- [ ] Implement vulnerability scanning in CI pipeline

---

## Scaling TODO

### Phase 1: Foundation (Critical — Do First)
- [ ] **Generate proper JWT secret**: Replace "change-me-in-production" with 256-bit random key
- [ ] **Implement rate limiting**: FastAPI middleware with Redis backend, 100 req/min default
- [ ] **Add refresh tokens**: 15-min access tokens + 30-day refresh tokens
- [ ] **Audit CSP headers**: Ensure Content-Security-Policy is correctly set in nginx
- [ ] **Add login attempt limiting**: Max 5 failed Google OAuth attempts per IP per hour
- [ ] **Implement token revocation**: Redis-based blocklist for logout and account re-linking
- [ ] **Add security headers**: All HTTP security headers in nginx configs
- [ ] **Symbol input validation**: Regex validation on all ticker symbol inputs
- [ ] **API payload size limits**: Max 1MB request body, max 500 char strings

### Phase 2: Scale
- [ ] **Add GitHub OAuth**: Second OAuth provider for developer users
- [ ] **RBAC system**: Admin, premium, free tiers with permission matrix
- [ ] **API key management**: Generate/revoke API keys for premium users
- [ ] **Authenticated WebSocket**: JWT-based WS auth with per-user message filtering
- [ ] **Brute force protection**: IP-based lockout after repeated failures
- [ ] **Security audit**: External penetration test by third-party firm
- [ ] **GDPR compliance**: Account deletion, data export, privacy policy
- [ ] **Dependency scanning**: Dependabot + Snyk for Python and npm vulnerabilities

### Phase 3: Global
- [ ] **Enterprise SSO**: SAML/OIDC for enterprise customers
- [ ] **Multi-factor auth**: TOTP-based 2FA for premium accounts
- [ ] **SOC2 certification**: Complete audit and certification process
- [ ] **PCI DSS** (if handling payments): Stripe/payment processor integration
- [ ] **Regional data residency**: EU data stays in EU region
- [ ] **Bug bounty program**: Public security vulnerability reporting
- [ ] **Zero-trust architecture**: Service mesh with mTLS between services

---

## Security Review Checklist (for all PRs)

- [ ] No secrets committed (API keys, passwords, tokens)
- [ ] No `# nosec` or `# type: ignore` for security-related code
- [ ] All user-facing endpoints use `Depends(get_current_user)`
- [ ] All queries on user data include `WHERE user_id = current_user.id`
- [ ] Input validation on all user-provided data (Pydantic + custom validators)
- [ ] No raw SQL — all queries through SQLAlchemy ORM
- [ ] Error messages don't leak internal state (no stack traces, no SQL errors)
- [ ] New dependencies scanned for known vulnerabilities
- [ ] CORS origins are explicit — no wildcard `*`
- [ ] Rate limiting applied to new endpoints if needed
