"""Provider factory - swap implementations via config."""

from app.core.config import settings
from app.providers.alpha_vantage_provider import AlphaVantageIPOProvider
from app.providers.base import IPOProvider, NewsProvider, QuoteProvider
from app.providers.finnhub_provider import (
    FinnhubIPOProvider,
    FinnhubNewsProvider,
    FinnhubQuoteProvider,
)

# Registry of available providers. Add new providers here.
NEWS_PROVIDERS: dict[str, type[NewsProvider]] = {
    "finnhub": FinnhubNewsProvider,
}

QUOTE_PROVIDERS: dict[str, type[QuoteProvider]] = {
    "finnhub": FinnhubQuoteProvider,
}

IPO_PROVIDERS: dict[str, type[IPOProvider]] = {
    "alphavantage": AlphaVantageIPOProvider,  # free tier, default
    "finnhub": FinnhubIPOProvider,            # premium only
}


def get_news_provider(name: str | None = None) -> NewsProvider:
    key = name or "finnhub"
    return NEWS_PROVIDERS[key]()


def get_quote_provider(name: str | None = None) -> QuoteProvider:
    key = name or "finnhub"
    return QUOTE_PROVIDERS[key]()


def get_ipo_provider(name: str | None = None) -> IPOProvider:
    key = name or settings.ipo_provider
    if key not in IPO_PROVIDERS:
        raise ValueError(f"Unknown IPO provider '{key}'. Choose from: {list(IPO_PROVIDERS)}")
    return IPO_PROVIDERS[key]()
