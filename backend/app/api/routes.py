"""API routes for the financial monitoring system."""

import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_google_user
from app.core.config import settings
from app.core.database import get_db
from app.models.models import (
    IPOEvent,
    NewsArticle,
    PriceAlert,
    Reminder,
    Ticker,
    User,
    UserWatchlist,
)
from app.providers.factory import get_quote_provider
from app.schemas.schemas import (
    ChatMessage,
    ChatResponse,
    IPOEventResponse,
    NewsArticleResponse,
    PriceAlertCreate,
    PriceAlertResponse,
    PriceAlertUpdate,
    ReminderCreate,
    ReminderResponse,
    TickerCreate,
    TickerResponse,
)
from app.services.chat import parse_chat_message
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Tickers  (per-user watchlist)
# ---------------------------------------------------------------------------

@router.get("/tickers", response_model=list[TickerResponse])
async def list_tickers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticker)
        .join(UserWatchlist, UserWatchlist.symbol == Ticker.symbol)
        .where(UserWatchlist.user_id == current_user.id)
        .order_by(Ticker.symbol)
    )
    return result.scalars().all()


@router.post("/tickers", response_model=TickerResponse, status_code=201)
async def add_ticker(
    payload: TickerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    symbol = payload.symbol.upper()

    existing_wl = await db.execute(
        select(UserWatchlist).where(
            UserWatchlist.user_id == current_user.id,
            UserWatchlist.symbol == symbol,
        )
    )
    if existing_wl.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"{symbol} already in your watchlist")

    existing_ticker = await db.execute(select(Ticker).where(Ticker.symbol == symbol))
    ticker = existing_ticker.scalar_one_or_none()
    if ticker is None:
        ticker = Ticker(
            symbol=symbol,
            name=payload.name or symbol,
            exchange=payload.exchange,
            active=True,
        )
        db.add(ticker)
        await db.flush()
        try:
            provider = get_quote_provider()
            quote = await provider.fetch_quote(symbol)
            ticker.last_price = quote.get("price")
            ticker.change_percent = quote.get("change_percent")
        except Exception:
            pass
    else:
        ticker.active = True

    db.add(UserWatchlist(user_id=current_user.id, symbol=symbol))
    await db.commit()
    await db.refresh(ticker)
    return ticker


@router.delete("/tickers/{symbol}", status_code=204)
async def remove_ticker(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(UserWatchlist).where(
            UserWatchlist.user_id == current_user.id,
            UserWatchlist.symbol == symbol.upper(),
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Ticker not in your watchlist")
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

@router.get("/news", response_model=list[NewsArticleResponse])
async def list_news(
    limit: int = Query(default=50, ge=1, le=200),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
    if category:
        query = query.where(NewsArticle.category == category)
    result = await db.execute(query)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# IPO Events
# ---------------------------------------------------------------------------

@router.get("/ipos", response_model=list[IPOEventResponse])
async def list_ipos(db: AsyncSession = Depends(get_db)):
    today = datetime.date.today()
    two_weeks = today + datetime.timedelta(days=14)
    result = await db.execute(
        select(IPOEvent)
        .where(IPOEvent.expected_date >= today, IPOEvent.expected_date <= two_weeks)
        .order_by(IPOEvent.expected_date)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

@router.post("/reminders", response_model=ReminderResponse, status_code=201)
async def create_reminder(
    payload: ReminderCreate,
    current_user: User = Depends(require_google_user),
    db: AsyncSession = Depends(get_db),
):
    ipo = await db.execute(select(IPOEvent).where(IPOEvent.id == payload.ipo_event_id))
    if not ipo.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="IPO event not found")
    if payload.notify_via not in ("email", "pagerduty"):
        raise HTTPException(status_code=400, detail="notify_via must be 'email' or 'pagerduty'")
    reminder = Reminder(**payload.model_dump(), user_id=current_user.id)
    db.add(reminder)
    await db.flush()
    return reminder


@router.get("/reminders", response_model=list[ReminderResponse])
async def list_reminders(
    current_user: User = Depends(require_google_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reminder)
        .where(Reminder.user_id == current_user.id)
        .order_by(Reminder.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/reminders/{reminder_id}", status_code=204)
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(require_google_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return None


# ---------------------------------------------------------------------------
# Price Alerts  (per-user)
# ---------------------------------------------------------------------------

@router.get("/alerts", response_model=list[PriceAlertResponse])
async def list_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PriceAlert)
        .where(PriceAlert.user_id == current_user.id)
        .order_by(PriceAlert.created_at.desc())
    )
    return result.scalars().all()


@router.post("/alerts", response_model=PriceAlertResponse, status_code=201)
async def create_alert(
    payload: PriceAlertCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if settings.alerts_require_premium and current_user.tier != "premium":
        raise HTTPException(
            status_code=403, detail="Threshold alerts require a premium subscription"
        )
    alert = PriceAlert(
        user_id=current_user.id,
        symbol=payload.symbol.upper(),
        threshold_pct=payload.threshold_pct,
        direction=payload.direction,
        is_premium_feature=True,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.put("/alerts/{alert_id}", response_model=PriceAlertResponse)
async def update_alert(
    alert_id: int,
    payload: PriceAlertUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PriceAlert).where(
            PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if payload.threshold_pct is not None:
        alert.threshold_pct = payload.threshold_pct
    if payload.direction is not None:
        alert.direction = payload.direction
    if payload.is_active is not None:
        alert.is_active = payload.is_active
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(PriceAlert).where(
            PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Chat  (per-user scoped)
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    parsed = parse_chat_message(payload.message)

    if parsed["action"] == "add_ticker":
        ticker_data = TickerCreate(symbol=parsed["ticker"])
        try:
            await add_ticker(ticker_data, current_user, db)
        except HTTPException:
            parsed["reply"] = f"{parsed['ticker']} is already in your watchlist."

    elif parsed["action"] == "remove_ticker":
        try:
            await remove_ticker(parsed["ticker"], current_user, db)
        except HTTPException:
            parsed["reply"] = f"{parsed['ticker']} is not in your watchlist."

    elif parsed["action"] == "list_tickers":
        tickers = await list_tickers(current_user, db)
        if tickers:
            symbols = ", ".join(t.symbol for t in tickers)
            parsed["reply"] = f"Your watchlist: {symbols}"
        else:
            parsed["reply"] = "Your watchlist is empty. Try 'add AAPL' to get started."

    return ChatResponse(
        reply=parsed["reply"],
        action=parsed["action"],
        ticker=parsed.get("ticker"),
    )


# ---------------------------------------------------------------------------
# Candles
# ---------------------------------------------------------------------------

_VALID_RESOLUTIONS = {"1", "5", "15", "30", "60", "D", "W"}
_YF_INTERVAL_MAP = {"1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "60m"}


def _yf_params(resolution: str, days: int) -> tuple[str, str]:
    if resolution in _YF_INTERVAL_MAP:
        return "1d", _YF_INTERVAL_MAP[resolution]
    if resolution == "D":
        if days <= 7:
            return "5d", "1d"
        if days <= 30:
            return "1mo", "1d"
        return "3mo", "1d"
    return "3mo", "1wk"


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    resolution: str = "5",
    days: int = Query(default=1, ge=1, le=365),
):
    """Fetch OHLCV candle data via Yahoo Finance. No API key required."""
    import asyncio

    import yfinance as yf

    if resolution not in _VALID_RESOLUTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid resolution '{resolution}'")

    period, interval = _yf_params(resolution, days)

    try:
        ticker_obj = yf.Ticker(symbol.upper())
        hist = await asyncio.get_event_loop().run_in_executor(
            None, lambda: ticker_obj.history(period=period, interval=interval)
        )
    except Exception:
        logger.exception("Failed to fetch candles for symbol=%s", symbol.upper())
        raise HTTPException(status_code=502, detail="Failed to fetch market data")

    if hist is None or hist.empty:
        return []

    return [
        {
            "t": int(ts.timestamp()),
            "o": round(float(row["Open"]), 4),
            "h": round(float(row["High"]), 4),
            "l": round(float(row["Low"]), 4),
            "c": round(float(row["Close"]), 4),
            "v": int(row["Volume"]),
        }
        for ts, row in hist.iterrows()
    ]


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await ws_manager.send_personal(websocket, "pong", {})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
