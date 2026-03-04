import datetime
import math

from pydantic import BaseModel, field_validator


# --- Ticker ---
class TickerCreate(BaseModel):
    symbol: str
    name: str = ""
    exchange: str = ""


class TickerResponse(BaseModel):
    id: int
    symbol: str
    name: str
    exchange: str
    last_price: float | None = None
    change_percent: float | None = None
    active: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

    @field_validator("last_price", "change_percent", mode="before")
    @classmethod
    def sanitize_float(cls, v: float | None) -> float | None:
        """Replace nan/inf with None — these are not valid JSON and crash serialization."""
        if v is None:
            return None
        return None if not math.isfinite(v) else v


# --- News ---
class NewsArticleResponse(BaseModel):
    id: int
    external_id: str
    headline: str
    summary: str
    source: str
    url: str
    image_url: str
    category: str
    related_tickers: str
    sentiment: str
    published_at: datetime.datetime
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- IPO ---
class IPOEventResponse(BaseModel):
    id: int
    company_name: str
    symbol: str
    exchange: str
    price_range: str
    shares_offered: str
    expected_date: datetime.date
    status: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- Reminder ---
class ReminderCreate(BaseModel):
    ipo_event_id: int
    notify_via: str  # "email" | "pagerduty"
    notify_address: str
    remind_before_hours: int = 24


class ReminderResponse(BaseModel):
    id: int
    ipo_event_id: int
    notify_via: str
    notify_address: str
    remind_before_hours: int
    sent: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- Chat ---
class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    action: str | None = None  # "added_ticker", "removed_ticker", None
    ticker: str | None = None


# --- WebSocket ---
class WSMessage(BaseModel):
    type: str  # "news", "quote", "ipo"
    data: dict
