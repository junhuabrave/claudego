# Security Implementation Best Practices

**Audience:** All engineering teams (Backend, Auth & Security, Frontend, DevOps, Test Engineering)
**Context:** Distilled from the 2026-03-08 security review and the cross-team sprint that followed.

---

## 1. Auth Layer Design — The Three-Tier Model

This is the pattern to use for every new endpoint. Ask yourself which tier the endpoint belongs to before writing a single line of handler code.

```
Tier 0 — Public (no identity required)
  Examples: GET /news, GET /ipos, GET /candles/{symbol}
  Rule: Public market data that has no user context whatsoever.
        No session header, no JWT — just serve it.

Tier 1 — Any session (anonymous OR Google-authenticated)
  Examples: GET /tickers, POST /chat, GET /alerts
  Dependency: Depends(get_current_user)
  Rule: Personalized features. Anonymous users get a real, scoped
        experience backed by their X-Session-ID. When they sign in
        via Google, their data migrates automatically.

Tier 2 — Google-authenticated only
  Examples: POST /reminders, GET /reminders, DELETE /reminders/{id}
  Dependency: Depends(require_google_user)
  Rule: Anything that persists beyond a browser session, sends
        real notifications, or is tied to a verified identity.
        Anonymous sessions are ephemeral — don't hang durable
        records off them.
```

**Decision rule:** If the endpoint stores a `notify_address`, sends an email, or would be confusing to own as an anonymous user — it's Tier 2.

---

## 2. Dependency Selection Cheat Sheet

```python
# Tier 1 — personalised but anonymous-friendly
async def my_endpoint(
    current_user: User = Depends(get_current_user),   # anon OR google
    db: AsyncSession = Depends(get_db),
): ...

# Tier 2 — requires real identity
async def my_endpoint(
    current_user: User = Depends(require_google_user), # google only → 403 if anon
    db: AsyncSession = Depends(get_db),
): ...

# Tier 0 — no identity at all
async def my_endpoint(
    db: AsyncSession = Depends(get_db),                # no current_user
): ...
```

`require_google_user` wraps `get_current_user` — it handles token resolution and then adds the identity check. You never call `get_current_user` manually and then check `google_id` yourself.

---

## 3. Data Isolation — Always Scope to the Owning User

Every query on a user-owned table must include a `user_id` filter. No exceptions.

```python
# ✅ Correct — user can only see their own rows
result = await db.execute(
    select(Reminder)
    .where(Reminder.user_id == current_user.id)
    .order_by(Reminder.created_at.desc())
)

# ✅ Correct — DELETE scoped to owner; rowcount=0 → 404, not a leak
result = await db.execute(
    delete(Reminder).where(
        Reminder.id == reminder_id,
        Reminder.user_id == current_user.id,
    )
)
if result.rowcount == 0:
    raise HTTPException(status_code=404, detail="Reminder not found")

# ❌ Wrong — returns all users' data, leaks PII
result = await db.execute(select(Reminder))
```

The `rowcount == 0 → 404` pattern is intentional: it gives no information about whether the row exists for another user versus doesn't exist at all.

---

## 4. Schema Validation — Validate at the API Boundary

Input validation happens in Pydantic schemas, not in route handlers. Handlers get clean, validated data or the request never reaches them.

```python
# String fields: always set a max_length matching the DB column
class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)  # matches String(100)

# Bounded text input
class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=500)

# Ticker symbols: accept both cases — the route normalises to uppercase on write
class TickerCreate(BaseModel):
    symbol: str = Field(pattern=r"^[\^]?[A-Za-z0-9.-]{1,20}$")
    # Note: accepts lowercase — route calls .upper() before storage.
    # Rejecting "aapl" at the schema level when the handler would have
    # accepted it creates a confusing API.

# Numeric bounds on query params — always explicit ge/le
limit: int = Query(default=50, ge=1, le=200)
days:  int = Query(default=1,  ge=1, le=365)
```

**Why max_length matters:** Without it, oversized input hits the DB column constraint and returns a raw `sqlalchemy.exc.DataError` to the client. With it, Pydantic returns a clean 422 before the DB is touched.

---

## 5. Error Handling — Never Leak Internals

```python
# ❌ Exposes exception type, stack trace path, and provider internals
raise HTTPException(status_code=502, detail=str(exc))

# ✅ Log the detail server-side, return a safe message to the client
except Exception:
    logger.exception("Failed to fetch candles for symbol=%s", symbol.upper())
    raise HTTPException(status_code=502, detail="Failed to fetch market data")
```

Rule: 4xx messages can be descriptive (the user needs to fix something). 5xx messages must be generic (don't tell an attacker what broke or how).

---

## 6. WebSocket — Never Broadcast User-Identifying Data

WebSocket connections are currently unauthenticated and use a broadcast model: every message goes to every connected client.

```python
# ❌ Live PII leak — all connected clients see every user's alert
broadcasts.append({
    "user_id": alert.user_id,   # ← remove this
    "symbol": alert.symbol,
    ...
})

# ✅ Strip any field that identifies a specific user
broadcasts.append({
    "alert_id": alert.id,
    # user_id intentionally excluded — broadcast reaches ALL connected clients
    "symbol": alert.symbol,
    ...
})
```

**Principle:** If a field would be sensitive if read by a stranger, it must not appear in a broadcast payload. Per-user delivery (Phase 2) will require JWT-based WebSocket authentication — that work is tracked in `auth-security.md`.

---

## 7. Secrets and Startup Guards

Secrets management has two rules:

1. **Never commit secrets** — use `.env` with `.env.example` placeholders
2. **Never let the app start with an insecure default** in production

```python
# Pydantic model validator — runs at import time when Settings() is constructed
@model_validator(mode="after")
def _validate_secrets(self) -> "Settings":
    if self.app_env != "development" and self.jwt_secret_key == _DEFAULT_JWT_SECRET:
        print("FATAL: JWT_SECRET_KEY is the default placeholder. "
              "Generate one: openssl rand -hex 32", file=sys.stderr)
        sys.exit(1)   # Hard exit — don't use raise ValueError here.
    return self       # ValueError can be caught/swallowed. sys.exit cannot.
```

**Why `sys.exit` not `raise`:** At `Settings()` construction time, application logging is not yet configured. A `ValueError` may be swallowed by the server framework's startup routine and produce a confusing error. `sys.exit(1)` with an explicit `print(stderr)` is guaranteed to be visible and terminal.

---

## 8. SMTP Security

Always construct an explicit SSL context — never call `starttls()` bare.

```python
# ❌ Vulnerable to MITM on the STARTTLS upgrade
server.starttls()

# ✅ Forces certificate validation on the TLS upgrade
import ssl
tls_context = ssl.create_default_context()
server.starttls(context=tls_context)
```

`ssl.create_default_context()` uses the system's trusted CA bundle and enforces hostname verification. The bare call does neither.

---

## 9. Database Migrations — Alembic, Not `create_all`

```python
# ❌ Never in production — silently skips columns that already exist,
#    can't roll back, leaves schema state unknown
Base.metadata.create_all(bind=engine)

# ✅ Every model change ships with an Alembic migration
alembic revision --autogenerate -m "alter_reminders_add_user_id"
alembic upgrade head
```

Migration naming convention: `alter_<table>_add_<column>`, `add_<table>`, `drop_<table>`.

For new non-nullable columns with no production data: go straight to `nullable=False` with no default. If production data exists: add nullable first → backfill → add constraint (two migrations).

---

## 10. Cross-Team Coordination — File Ownership

File ownership is defined in each team's `*.md` under `.claude/teams/`. The short version:

| File | Owner | Coordinate before touching |
|---|---|---|
| `core/auth.py` | Auth & Security | Auth team writes, Backend wires |
| `core/config.py` | Auth & Security | Auth team for auth-related settings |
| `models/models.py` (User columns) | Auth & Security | Auth team sign-off on schema changes |
| `api/routes.py` | Backend | Auth team mandatory reviewer |
| `schemas/schemas.py` | Backend | Auth team for validation patterns |
| `services/` | Backend | — |
| `tests/security/` | Test Eng + Auth | Joint ownership |

**What we learned this sprint:**

- **Communicate the exact code, not just the intent.** Auth team's reply included the verbatim `require_google_user` function. That let Backend wire it immediately, hours before the PR landed.
- **Watch for overlapping ownership.** Both Backend and Auth touched `config.py` independently (startup guard). Catch this early by scanning the diff against main before opening your PR — resolve it before it becomes a merge conflict.
- **Regex specs need the full context.** The initial symbol pattern `^[\^]?[A-Z0-9.-]{1,20}$` was correct in intent but would have rejected `"aapl"` submitted by the frontend before the route's `.upper()` normalised it. Auth team caught this and corrected to `[A-Za-z0-9.-]`. Always think about where in the request lifecycle validation runs.

---

## 11. PR Checklist Additions (security-specific)

Add these to the existing Backend PR checklist:

- [ ] Endpoint tier identified (Tier 0 / 1 / 2) and correct dependency used
- [ ] All user-owned table queries include `WHERE user_id = current_user.id`
- [ ] No raw exception messages in `detail=` (5xx responses use generic messages)
- [ ] No `user_id` or PII added to WebSocket broadcast payloads
- [ ] New `str` columns have `max_length` in Pydantic schema matching DB column size
- [ ] New query params have explicit `ge`/`le` bounds via `Query(...)`
- [ ] Model changes have an Alembic migration (`alembic/versions/`)
- [ ] Auth & Security tagged as mandatory reviewer

---

*Authored by Backend Python team · Security review sprint 2026-03-09*
*Reviewed by Auth & Security team*
