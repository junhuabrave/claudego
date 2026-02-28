"""Provider factory - swap implementations via config."""

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
    "finnhub": FinnhubIPOProvider,
}

# Default provider keys - change these or make them config-driven
_DEFAULT_NEWS = "finnhub"
_DEFAULT_QUOTE = "finnhub"
_DEFAULT_IPO = "finnhub"


def get_news_provider(name: str | None = None) -> NewsProvider:
    key = name or _DEFAULT_NEWS
    return NEWS_PROVIDERS[key]()


def get_quote_provider(name: str | None = None) -> QuoteProvider:
    key = name or _DEFAULT_QUOTE
    return QUOTE_PROVIDERS[key]()


def get_ipo_provider(name: str | None = None) -> IPOProvider:
    key = name or _DEFAULT_IPO
    return IPO_PROVIDERS[key]()
