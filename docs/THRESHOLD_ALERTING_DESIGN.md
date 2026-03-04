# Threshold Alerting — Design Document

> **Status:** Ready for implementation
> **Scope:** Per-user, per-ticker price movement alerts delivered via WebSocket push.
> **Premium note:** Scaffolded as a premium feature (single env flag gates it), but enabled for all users by default.

---

## Overview

When a ticker in the watchlist moves up or down by more than a user-configured percentage,
the browser receives a real-time push notification (MUI Snackbar) without any page interaction.

```
User sets alert: AAPL, threshold 5%, direction "up"
      │
      ▼
poll_quotes fires (every 30s)
      │
      ├─► updates Ticker.change_percent in DB
      │
      └─► check_price_alerts(quotes)
            │  change_percent >= 5.0? direction matches?
            │  not in cooldown?
            └─► ws_manager.broadcast("alert", {...})
                      │
                      ▼
              Browser Snackbar: "AAPL is up 5.3% today ▲ $157.50"
```

**No email delivery in this phase** — WebSocket push only. Email can be layered on later
using the existing `notification.py` (same pattern as IPO reminders).

---

## 1. Session Identity (no-auth approach)

There is currently no authentication. To support per-user alerts without adding auth:

- On first load the frontend generates a UUID (`crypto.randomUUID()`) and stores it in
  `localStorage` as `finmonitor_session_id`.
- Every API request includes it as the `X-Session-ID` header (set in `services/api.ts`).
- The backend reads it from `request.headers.get("X-Session-ID", "")`.
- When auth is added later, replace `session_id` with `user_id` — the DB schema and API
  contract don't change, only where the identity comes from.

> Session IDs are not secrets — they identify a browser, not a person. Treat them like an
> anonymous visitor cookie.

---

## 2. Database

### New model: `PriceAlert`

**File:** `backend/app/models/models.py`

```python
class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, index=True)          # client identifier
    symbol: Mapped[str] = mapped_column(String, index=True)              # e.g. "AAPL", "^KS11"
    threshold_pct: Mapped[float] = mapped_column(Float)                  # e.g. 5.0 = 5%
    direction: Mapped[str] = mapped_column(String, default="both")       # "up" | "down" | "both"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_premium_feature: Mapped[bool] = mapped_column(Boolean, default=False)  # intent marker
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Field notes:**
- `direction`: `"up"` — only alert when change_percent >= +threshold; `"down"` — only when
  <= -threshold; `"both"` — either.
- `triggered_at`: tracks the last time this alert fired. Used for cooldown (see §4).
- `is_premium_feature`: documents intent; not used for access control until the gate is
  enabled (see §7).

**Migration:** SQLAlchemy `Base.metadata.create_all` will auto-create the table on first
startup (same as existing tables — no Alembic needed for this project's setup).

---

## 3. Pydantic Schemas

**File:** `backend/app/schemas/schemas.py`

```python
# --- Requests ---

class PriceAlertCreate(BaseModel):
    symbol: str
    threshold_pct: float = Field(gt=0, le=100)   # 0 < x <= 100
    direction: str = Field(default="both", pattern="^(up|down|both)$")

class PriceAlertUpdate(BaseModel):
    threshold_pct: float | None = Field(default=None, gt=0, le=100)
    direction: str | None = Field(default=None, pattern="^(up|down|both)$")
    is_active: bool | None = None

# --- Responses ---

class PriceAlertResponse(BaseModel):
    id: int
    symbol: str
    threshold_pct: float
    direction: str
    is_active: bool
    triggered_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

## 4. API Endpoints

**File:** `backend/app/api/routes.py`

All alert endpoints read `session_id` from the `X-Session-ID` request header.
If the header is missing or empty, return `400 Bad Request`.

| Method | Path | Request body | Response | Notes |
|--------|------|-------------|----------|-------|
| `GET` | `/api/alerts` | — | `list[PriceAlertResponse]` | Scoped to session |
| `POST` | `/api/alerts` | `PriceAlertCreate` | `PriceAlertResponse` (201) | Premium gate here |
| `PUT` | `/api/alerts/{id}` | `PriceAlertUpdate` | `PriceAlertResponse` | 404 if wrong session |
| `DELETE` | `/api/alerts/{id}` | — | 204 | 404 if wrong session |

### POST `/api/alerts` — full implementation sketch

```python
@router.post("/alerts", response_model=PriceAlertResponse, status_code=201)
async def create_alert(
    payload: PriceAlertCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    session_id = request.headers.get("X-Session-ID", "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")

    # Premium gate — flip ALERTS_REQUIRE_PREMIUM=true in env to restrict
    if settings.alerts_require_premium:
        raise HTTPException(status_code=403, detail="Threshold alerts require a premium subscription")

    alert = PriceAlert(
        session_id=session_id,
        symbol=payload.symbol.upper(),
        threshold_pct=payload.threshold_pct,
        direction=payload.direction,
        is_premium_feature=True,  # marks intent regardless of gate state
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert
```

---

## 5. Config

**File:** `backend/app/core/config.py`

```python
# Threshold alerts
alerts_require_premium: bool = False   # set True to gate feature for premium users only
alert_cooldown_minutes: int = 60       # minimum minutes between re-firing the same alert
```

**File:** `backend/.env.example`

```bash
# Threshold alerts
ALERTS_REQUIRE_PREMIUM=false     # set true to restrict to premium users
ALERT_COOLDOWN_MINUTES=60        # how long before the same alert can fire again
```

---

## 6. Alert Evaluation Logic

**File:** `backend/app/services/scheduler.py`

Extract into a standalone async function called from `poll_quotes` after the DB update.

```python
ALERT_COOLDOWN_MINUTES = settings.alert_cooldown_minutes  # default 60

async def check_price_alerts(quotes: list[dict]) -> None:
    """
    Compare freshly-polled quotes against active PriceAlert rows.
    Broadcast a WebSocket "alert" message for each threshold crossed.
    """
    if not quotes:
        return

    symbol_to_quote = {q["symbol"]: q for q in quotes}

    async with async_session() as session:
        result = await session.execute(
            select(PriceAlert).where(
                PriceAlert.is_active.is_(True),
                PriceAlert.symbol.in_(list(symbol_to_quote.keys())),
            )
        )
        alerts = result.scalars().all()

    now = datetime.datetime.now(datetime.timezone.utc)
    cooldown = datetime.timedelta(minutes=ALERT_COOLDOWN_MINUTES)

    triggered_ids: list[int] = []
    broadcasts: list[dict] = []

    for alert in alerts:
        quote = symbol_to_quote.get(alert.symbol)
        if not quote or quote.get("change_percent") is None:
            continue

        change = quote["change_percent"]  # float, e.g. 5.3 or -2.1

        # Determine if threshold is crossed in the right direction
        crossed = False
        if alert.direction == "up" and change >= alert.threshold_pct:
            crossed = True
        elif alert.direction == "down" and change <= -alert.threshold_pct:
            crossed = True
        elif alert.direction == "both" and abs(change) >= alert.threshold_pct:
            crossed = True

        if not crossed:
            continue

        # Cooldown: skip if fired recently
        if alert.triggered_at and (now - alert.triggered_at) < cooldown:
            continue

        triggered_ids.append(alert.id)
        broadcasts.append({
            "alert_id": alert.id,
            "session_id": alert.session_id,
            "symbol": alert.symbol,
            "threshold_pct": alert.threshold_pct,
            "direction": alert.direction,
            "actual_change_pct": round(change, 2),
            "current_price": quote.get("price", 0),
            "triggered_at": now.isoformat(),
        })

    # Persist triggered_at timestamps
    if triggered_ids:
        async with async_session() as session:
            await session.execute(
                update(PriceAlert)
                .where(PriceAlert.id.in_(triggered_ids))
                .values(triggered_at=now)
            )
            await session.commit()

    # Broadcast each alert individually so frontend can match by session_id
    for payload in broadcasts:
        await ws_manager.broadcast("alert", payload)
```

### Hooking into `poll_quotes`

```python
async def poll_quotes():
    ...
    await ws_manager.broadcast("quotes", {"quotes": quotes})

    # NEW: check thresholds after broadcasting updated prices
    await check_price_alerts(quotes)

    logger.info("Updated quotes for %d tickers", len(quotes))
```

### Why broadcast to all connections?

The WebSocket is currently a single shared channel — there is no per-session routing.
The frontend filters incoming `"alert"` messages by comparing `payload.session_id` against
the locally-stored session ID; messages for other sessions are silently ignored.

When per-user channels are needed in the future, add a `session_id → [WebSocket]` mapping
in `ConnectionManager` and use `send_personal` instead of `broadcast`.

---

## 7. WebSocket Protocol Addition

### New message type: `"alert"`

Sent by the server, received by the frontend.

```json
{
  "type": "alert",
  "data": {
    "alert_id": 42,
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "symbol": "AAPL",
    "threshold_pct": 5.0,
    "direction": "up",
    "actual_change_pct": 5.3,
    "current_price": 157.50,
    "triggered_at": "2026-03-04T10:15:00Z"
  }
}
```

No change is needed in `websocket_manager.py` — `broadcast()` already handles arbitrary
message types.

---

## 8. Frontend

### 8a. Session ID utility

**File:** `frontend/src/services/session.ts` *(new)*

```typescript
const KEY = "finmonitor_session_id";

export function getSessionId(): string {
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(KEY, id);
  }
  return id;
}
```

**Wire into Axios client** (`frontend/src/services/api.ts`):

```typescript
import { getSessionId } from "./session";

const api = axios.create({ baseURL: ... });

api.interceptors.request.use((config) => {
  config.headers["X-Session-ID"] = getSessionId();
  return config;
});
```

### 8b. TypeScript types

**File:** `frontend/src/types/index.ts` — add:

```typescript
export interface PriceAlert {
  id: number;
  symbol: string;
  threshold_pct: number;
  direction: "up" | "down" | "both";
  is_active: boolean;
  triggered_at: string | null;
  created_at: string;
}

export interface AlertTriggered {   // shape of WS "alert" data payload
  alert_id: number;
  session_id: string;
  symbol: string;
  threshold_pct: number;
  direction: string;
  actual_change_pct: number;
  current_price: number;
  triggered_at: string;
}
```

### 8c. API service methods

**File:** `frontend/src/services/api.ts` — add:

```typescript
export const alertsApi = {
  list: (): Promise<PriceAlert[]> =>
    api.get("/alerts").then(r => r.data),

  create: (payload: { symbol: string; threshold_pct: number; direction: string }): Promise<PriceAlert> =>
    api.post("/alerts", payload).then(r => r.data),

  update: (id: number, payload: Partial<{ threshold_pct: number; direction: string; is_active: boolean }>): Promise<PriceAlert> =>
    api.put(`/alerts/${id}`, payload).then(r => r.data),

  remove: (id: number): Promise<void> =>
    api.delete(`/alerts/${id}`).then(() => undefined),
};
```

### 8d. AlertsDialog component

**File:** `frontend/src/components/AlertsDialog.tsx` *(new)*

**Purpose:** Manage all alerts for a specific ticker.
**Opened from:** WatchList row — bell icon button (new column).

**Props:**
```typescript
interface Props {
  open: boolean;
  symbol: string;
  onClose: () => void;
}
```

**UI layout:**
```
┌─────────────────────────────────────────────┐
│  🔔 Price Alerts — AAPL                 [×] │
├─────────────────────────────────────────────┤
│  Add new alert                              │
│  Threshold: [  5  ] %   Direction: [Both ▼] │
│                              [Add Alert]    │
├─────────────────────────────────────────────┤
│  Active alerts                              │
│  ▲ Up ≥ 3%     active  [toggle] [delete]    │
│  ▼ Down ≥ 5%   active  [toggle] [delete]    │
│  (empty state: "No alerts set for AAPL")    │
└─────────────────────────────────────────────┘
```

**Implementation notes:**
- Fetches alerts on `open=true` via `alertsApi.list()`, filtered client-side by `symbol`.
- Alternatively, add `GET /api/alerts?symbol=AAPL` to the backend to filter server-side.
- Toggle calls `alertsApi.update(id, { is_active: !alert.is_active })`.
- Delete calls `alertsApi.remove(id)`.
- Loading and error states required.

### 8e. WatchList changes

**File:** `frontend/src/components/WatchList.tsx`

Add a bell icon button to each row:

```typescript
// New prop
interface Props {
  tickers: Ticker[];
  onRemove: (symbol: string) => void;
  onSelectSymbol: (ticker: Ticker) => void;
  onManageAlerts: (symbol: string) => void;   // NEW
}

// In table row Actions cell:
<Tooltip title="Manage alerts">
  <IconButton size="small" onClick={() => onManageAlerts(ticker.symbol)}>
    <NotificationsNoneIcon fontSize="small" />
  </IconButton>
</Tooltip>
```

### 8f. Dashboard — AlertsDialog state + WS handler

**File:** `frontend/src/pages/Dashboard.tsx`

```typescript
// State
const [alertsSymbol, setAlertsSymbol] = useState<string | null>(null);
const [activeAlerts, setActiveAlerts] = useState<AlertTriggered[]>([]);

// WS handler addition (in handleWSMessage switch)
case "alert": {
  const payload = msg.data as AlertTriggered;
  if (payload.session_id !== getSessionId()) break;  // ignore other sessions
  setActiveAlerts(prev => [payload, ...prev]);
  break;
}

// Render additions
<WatchList
  ...
  onManageAlerts={(symbol) => setAlertsSymbol(symbol)}
/>

{alertsSymbol && (
  <AlertsDialog
    open={true}
    symbol={alertsSymbol}
    onClose={() => setAlertsSymbol(null)}
  />
)}

// Toast for triggered alerts (one Snackbar per alert, auto-dismiss 8s)
{activeAlerts.map((a) => (
  <Snackbar
    key={a.alert_id}
    open
    autoHideDuration={8000}
    onClose={() => setActiveAlerts(prev => prev.filter(x => x.alert_id !== a.alert_id))}
    anchorOrigin={{ vertical: "top", horizontal: "right" }}
  >
    <Alert severity={a.actual_change_pct >= 0 ? "success" : "error"} variant="filled">
      <strong>{a.symbol}</strong> {a.actual_change_pct >= 0 ? "▲" : "▼"}
      {Math.abs(a.actual_change_pct).toFixed(2)}% today — ${a.current_price.toFixed(2)}
    </Alert>
  </Snackbar>
))}
```

---

## 9. Premium Feature Gate (summary)

| Location | What to add |
|----------|-------------|
| `config.py` | `alerts_require_premium: bool = False` |
| `.env.example` | `ALERTS_REQUIRE_PREMIUM=false` |
| `POST /api/alerts` | `if settings.alerts_require_premium: raise HTTPException(403, ...)` |
| `PriceAlert` model | `is_premium_feature: bool = True` (intent marker, not a runtime check) |

**To gate the feature later:** set `ALERTS_REQUIRE_PREMIUM=true` in the deployed
environment (Secrets Manager for prod, `.env` locally). No code change needed.

---

## 10. File Change Checklist

```
backend/
  app/models/models.py          — add PriceAlert model
  app/schemas/schemas.py        — add PriceAlertCreate, PriceAlertUpdate, PriceAlertResponse
  app/api/routes.py             — add GET/POST/PUT/DELETE /api/alerts
  app/core/config.py            — add alerts_require_premium, alert_cooldown_minutes
  app/services/scheduler.py     — add check_price_alerts(), call from poll_quotes()
  .env.example                  — add ALERTS_REQUIRE_PREMIUM, ALERT_COOLDOWN_MINUTES

frontend/
  src/services/session.ts       — new: getSessionId()
  src/services/api.ts           — add X-Session-ID interceptor + alertsApi methods
  src/types/index.ts            — add PriceAlert, AlertTriggered interfaces
  src/components/AlertsDialog.tsx    — new: manage alerts for a ticker
  src/components/WatchList.tsx       — add bell icon button + onManageAlerts prop
  src/pages/Dashboard.tsx            — add AlertsDialog state, WS "alert" handler, Snackbars
```

No changes needed to: `websocket_manager.py`, `notification.py`, `nginx.conf`, Docker setup,
or any existing API endpoints.

---

## 11. Open Questions / Future Work

| Topic | Decision needed |
|-------|----------------|
| Alert basis | This design uses **daily change_percent** (vs. previous close, polled every 30s). An alternative is **real-time movement** (price N% above/below the price at alert creation time). Latter requires storing a `baseline_price` on the alert and comparing against `last_price`. |
| Alert reset | Currently alerts re-fire after the cooldown regardless of direction. Should a "down 5%" alert auto-disable once triggered, requiring the user to re-enable? |
| Multi-tab / multi-device | Two browser tabs share the same `session_id` (same localStorage). This is correct behaviour — both will receive the same alerts. |
| Email delivery | The SMTP infrastructure from IPO reminders already exists. To add email delivery: add `notify_via: "browser" \| "email"` field and call `notification.py` in `check_price_alerts` when `notify_via == "email"`. |
| Auth migration | When auth is added: replace `session_id` header with JWT claim. Update the `select(PriceAlert).where(PriceAlert.session_id == ...)` queries to filter by `user_id` instead. |
```
