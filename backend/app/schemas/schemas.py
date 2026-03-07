import datetime
import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- User ---
class UserResponse(BaseModel):
    id: int
    email: str | None = None
    display_name: str
    tier: str
    public_profile: bool
    is_anonymous: bool = False
    # google_id is read from the ORM object to compute is_anonymous,
    # but excluded from the JSON response so it is never sent to the client.
    google_id: str | None = Field(default=None, exclude=True, repr=False)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_is_anonymous(self) -> "UserResponse":
        self.is_anonymous = self.google_id is None
        return self


class UserUpdate(BaseModel):
    display_name: str | None = None


# --- Price Alerts ---
class PriceAlertCreate(BaseModel):
    symbol: str
    threshold_pct: float = Field(gt=0, le=100)
    direction: str = Field(default="both", pattern="^(up|down|both)$")


class PriceAlertUpdate(BaseModel):
    threshold_pct: float | None = Field(default=None, gt=0, le=100)
    direction: str | None = Field(default=None, pattern="^(up|down|both)$")
    is_active: bool | None = None


class PriceAlertResponse(BaseModel):
    id: int
    symbol: str
    threshold_pct: float
    direction: str
    is_active: bool
    triggered_at: datetime.datetime | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


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
