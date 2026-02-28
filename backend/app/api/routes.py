"""API routes for the financial monitoring system."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import IPOEvent, NewsArticle, Reminder, Ticker
from app.providers.factory import get_quote_provider
from app.schemas.schemas import (
    ChatMessage,
    ChatResponse,
    IPOEventResponse,
    NewsArticleResponse,
    ReminderCreate,
    ReminderResponse,
    TickerCreate,
    TickerResponse,
)
from app.services.chat import parse_chat_message
from app.services.websocket_manager import ws_manager

router = APIRouter()


# --- Tickers ---
@router.get("/tickers", response_model=list[TickerResponse])
async def list_tickers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticker).where(Ticker.active.is_(True)).order_by(Ticker.symbol))
    return result.scalars().all()


@router.post("/tickers", response_model=TickerResponse, status_code=201)
async def add_ticker(payload: TickerCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Ticker).where(Ticker.symbol == payload.symbol.upper()))
    ticker = existing.scalar_one_or_none()
    if ticker:
        if not ticker.active:
            ticker.active = True
            await db.flush()
            return ticker
        raise HTTPException(status_code=409, detail=f"{payload.symbol} already in watchlist")

    # Fetch initial quote
    name = payload.name
    if not name:
        name = payload.symbol.upper()

    ticker = Ticker(
        symbol=payload.symbol.upper(),
        name=name,
        exchange=payload.exchange,
        active=True,
    )
    db.add(ticker)
    await db.flush()

    try:
        provider = get_quote_provider()
        quote = await provider.fetch_quote(payload.symbol.upper())
        ticker.last_price = quote.get("price")
        ticker.change_percent = quote.get("change_percent")
    except Exception:
        pass

    return ticker


@router.delete("/tickers/{symbol}", status_code=204)
async def remove_ticker(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticker).where(Ticker.symbol == symbol.upper()))
    ticker = result.scalar_one_or_none()
    if not ticker:
        raise HTTPException(status_code=404, detail="Ticker not found")
    ticker.active = False
    return None


# --- News ---
@router.get("/news", response_model=list[NewsArticleResponse])
async def list_news(
    limit: int = 50,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
    if category:
        query = query.where(NewsArticle.category == category)
    result = await db.execute(query)
    return result.scalars().all()


# --- IPO Events ---
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


# --- Reminders ---
@router.post("/reminders", response_model=ReminderResponse, status_code=201)
async def create_reminder(payload: ReminderCreate, db: AsyncSession = Depends(get_db)):
    # Validate IPO event exists
    ipo = await db.execute(select(IPOEvent).where(IPOEvent.id == payload.ipo_event_id))
    if not ipo.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="IPO event not found")

    if payload.notify_via not in ("email", "pagerduty"):
        raise HTTPException(status_code=400, detail="notify_via must be 'email' or 'pagerduty'")

    reminder = Reminder(**payload.model_dump())
    db.add(reminder)
    await db.flush()
    return reminder


@router.get("/reminders", response_model=list[ReminderResponse])
async def list_reminders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reminder).order_by(Reminder.created_at.desc()))
    return result.scalars().all()


@router.delete("/reminders/{reminder_id}", status_code=204)
async def delete_reminder(reminder_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(Reminder).where(Reminder.id == reminder_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return None


# --- Chat ---
@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatMessage, db: AsyncSession = Depends(get_db)):
    parsed = parse_chat_message(payload.message)

    if parsed["action"] == "add_ticker":
        ticker_data = TickerCreate(symbol=parsed["ticker"])
        try:
            await add_ticker(ticker_data, db)
        except HTTPException:
            parsed["reply"] = f"{parsed['ticker']} is already in your watchlist."

    elif parsed["action"] == "remove_ticker":
        try:
            await remove_ticker(parsed["ticker"], db)
        except HTTPException:
            parsed["reply"] = f"{parsed['ticker']} is not in your watchlist."

    elif parsed["action"] == "list_tickers":
        tickers = await list_tickers(db)
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


# --- WebSocket ---
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send ping / subscribe messages; for now just keep alive
            if data == "ping":
                await ws_manager.send_personal(websocket, "pong", {})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
